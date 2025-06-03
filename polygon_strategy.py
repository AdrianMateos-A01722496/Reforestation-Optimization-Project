from typing import List, Tuple, Dict
import pandas as pd
import numpy as np
from optimization_framework import (
    OptimizationStrategy, SupplyChainState, Order, PlantingActivity,
    TransportationActivity
)
from utils import (
    calculate_order_cost, get_treatment_time, calculate_planting_cost,
    calculate_transport_cost, calculate_total_activity_time,
    check_labor_hours_constraint, get_cheapest_provider_for_species,
    get_available_providers_for_species,
    VAN_CAPACITY, WAREHOUSE_CAPACITY, MAX_PLANTS_ORDER_PER_PROVIDER_PER_DAY,
    BASE_ID, LABOR_TIME, PLANTATION_COST_PER_PLANT, PROVIDER_COSTS, SPECIES_IDS,
    SPECIES_PROPORTIONS, WAREHOUSE_PROPORTIONS, PROVIDER_SPECIES
)

class PolygonStrategy(OptimizationStrategy):
    def __init__(self, state: SupplyChainState, time_matrix: pd.DataFrame):
        super().__init__(state)
        self.time_matrix = time_matrix
        # Convert column names to integers for consistent indexing
        self.time_matrix.columns = self.time_matrix.columns.astype(int)
        # Set diagonal to infinity to avoid selecting P18
        self.time_matrix.loc[BASE_ID, BASE_ID] = np.inf
        
        print(f"\nStarting optimization strategy...")
        print(f"Initial demand: {self.state.remaining_demand.sum().sum():,} plants")
    
    def solve(self) -> None:
        """Solve the optimization problem using a polygon-based strategy"""
        print("\nStarting optimization strategy...")
        print(f"Initial demand: {self.state.remaining_demand.sum().sum():,} plants")
        
        # Safety measures to prevent infinite loops
        max_days = 1000  # Reasonable upper limit 
        days_without_progress = 0
        max_days_without_progress = 20  # If no progress for 20 days, something is wrong
        last_demand = self.state.remaining_demand.sum().sum()
        
        while (not self.state.remaining_demand.empty and 
               self.state.remaining_demand.sum().sum() > 0 and
               self.state.current_day < max_days):
            
            current_demand = self.state.remaining_demand.sum().sum()
            current_inventory = self.state.get_total_warehouse_inventory()
            
            # Check for progress
            if current_demand < last_demand:
                days_without_progress = 0  # Reset counter
                last_demand = current_demand
            else:
                days_without_progress += 1
                if days_without_progress >= max_days_without_progress:
                    print(f"\n⚠️  No progress for {max_days_without_progress} days - stopping to avoid infinite loop")
                    print(f"Current demand: {current_demand:,}")
                    print(f"Current inventory: {current_inventory:,}")
                    break
            
            # Report progress regularly
            if self.state.current_day % 20 == 0 or current_demand < 5000:
                print(f"\nDay {self.state.current_day}:")
                print(f"- Remaining demand: {current_demand:,} plants")
                print(f"- Warehouse inventory: {current_inventory:,} plants")
                completion_pct = (1 - current_demand / 95588) * 100
                print(f"- Project completion: {completion_pct:.1f}%")
                
                # More frequent reporting when close to completion
                if current_demand < 1000:
                    print("🔥 FINAL PHASE - Close to completion!")
                    print("Species breakdown of remaining demand:")
                    for i in range(1, 11):
                        species_demand = self.state.remaining_demand[i].sum()
                        if species_demand > 0:
                            print(f"  Species {i}: {species_demand:,} plants needed")
            
            # Check if it's a weekend
            is_weekend = self.state.is_weekend(self.state.current_day)
            if is_weekend:
                # Still try to order plants on weekends
                ordered = self._order_plants_if_needed()
                if not ordered and current_demand < 1000:
                    print("Weekend: no orders placed, skipping to next day")
            else:
                # Try to plant available plants first
                planted_any = self._plant_available_plants()
                
                # If we couldn't plant anything or have remaining labor time, try to order
                if not planted_any or self.state.remaining_labor_hours > 0:
                    self._order_plants_if_needed()
            
            # Advance to next day
            self.state.advance_day()
        
        print("\nOptimization completed!")
        if self.state.current_day >= max_days:
            print(f"⚠️  Reached maximum day limit ({max_days})")
        elif days_without_progress >= max_days_without_progress:
            print(f"⚠️  Stopped due to lack of progress")
        else:
            print("🎉 All demand completed successfully!")
        
        print(f"Total cost: ${self.state.total_cost:,.2f}")
        print(f"Total days: {self.state.current_day}")
        
        final_demand = self.state.remaining_demand.sum().sum()
        print(f"Final demand: {final_demand:,} plants")
        
        if final_demand > 0:
            print("\nRemaining demand by species:")
            for i in range(1, 11):
                species_demand = self.state.remaining_demand[i].sum()
                if species_demand > 0:
                    inventory = self.state.available_inventory[i]
                    print(f"  Species {i}: {species_demand:,} needed, {inventory:,} available")
        
        print(f"Final warehouse inventory: {self.state.get_total_warehouse_inventory():,} plants")
    
    def _get_next_polygon(self) -> int:
        """Get the next polygon to reforest based on travel time from P18"""
        # Get polygons with remaining demand
        polygons_with_demand = self.state.remaining_demand[
            self.state.remaining_demand.sum(axis=1) > 0
        ].index.tolist()
        
        if len(polygons_with_demand) == 0:
            return None
        
        # Get travel times from P18 to all polygons with demand
        polygon_times = {}
        for polygon_id in polygons_with_demand:
            try:
                travel_time = self.time_matrix.loc[BASE_ID, polygon_id]
                polygon_times[polygon_id] = travel_time
            except KeyError:
                print(f"Warning: No travel time data for polygon {polygon_id}")
                continue
        
        if not polygon_times:
            return None
        
        # Return the closest polygon that has demand
        closest_polygon = min(polygon_times, key=polygon_times.get)
        return closest_polygon
    
    def _calculate_max_plants_per_day(self, polygon_id: int) -> int:
        """Calculate maximum number of plants that can be planted in a day for a given polygon"""
        # Get travel times
        travel_to = self.time_matrix.loc[BASE_ID, polygon_id]
        travel_back = self.time_matrix.loc[polygon_id, BASE_ID]
        
        # Calculate time per round trip (travel + load/unload)
        load_unload_time = 1.0  # 0.5 + 0.5 hours
        trip_time = travel_to + travel_back + load_unload_time
        
        # Calculate how many trips we can make in a day
        max_trips = int(LABOR_TIME / trip_time)
        
        # Calculate total plants we can transport
        max_plants = max_trips * VAN_CAPACITY
        
        print(f"Capacity calculation for polygon {polygon_id}:")
        print(f"- Trip time: {trip_time:.2f}h, Max trips: {max_trips}, Max plants: {max_plants:,}")
        
        return max_plants
    
    def _order_plants_if_needed(self) -> bool:
        """Order plants if needed and there's warehouse space"""
        # Check available warehouse space
        current_inventory = self.state.get_total_warehouse_inventory()
        available_space = WAREHOUSE_CAPACITY - current_inventory
        
        # Account for pending arrivals
        tomorrow_arrivals = sum(
            sum(quantity for _, quantity in order.species_id_quantity)
            for order in self.state.orders
            if order.arrival_day == self.state.current_day + 1
        )
        
        effective_space = available_space - tomorrow_arrivals
        
        if effective_space < VAN_CAPACITY:  # Need at least one van's worth of space
            print(f"Not enough warehouse space: {effective_space} available")
            return False
        
        # Get next polygon to understand what species we need
        polygon_id = self._get_next_polygon()
        if polygon_id is None:
            print("No polygons with remaining demand")
            return False
        
        # Get demand for next polygon
        polygon_demand = self.state.remaining_demand.loc[polygon_id]
        
        # Determine what to order based on current inventory levels and next polygon needs
        order_created = False
        
        # Simple provider rotation: cycle through providers based on day
        providers = ['laguna_seca', 'venado', 'moctezuma']
        primary_provider = providers[self.state.current_day % 3]
        
        # Try providers in rotation order, starting with primary
        provider_order = [primary_provider] + [p for p in providers if p != primary_provider]
        
        for provider in provider_order:
            if order_created:
                break
                
            # Get species this provider actually supplies (from PROVIDER_COSTS)
            available_species = list(PROVIDER_COSTS[provider].keys())
            order_quantities = []
            
            # Prioritize species needed for the next polygon
            species_priority = []
            
            # First, add species needed for next polygon that this provider supplies
            for species_id in available_species:
                polygon_need = polygon_demand[species_id] if polygon_demand[species_id] > 0 else 0
                available = self.state.available_inventory[species_id]
                total_demand = self.state.remaining_demand[species_id].sum()
                
                if polygon_need > 0 and total_demand > 0:
                    species_priority.append((species_id, polygon_need, total_demand))
                    print(f"Priority species {species_id}: polygon needs {polygon_need}, we have {available}, total demand {total_demand}")
            
            # Then add other species this provider supplies that we're low on
            for species_id in available_species:
                if species_id not in [s[0] for s in species_priority]:
                    available = self.state.available_inventory[species_id]
                    total_demand = self.state.remaining_demand[species_id].sum()
                    
                    if total_demand > 0 and available < VAN_CAPACITY * 2:
                        species_priority.append((species_id, 0, total_demand))
            
            # Sort by polygon need first, then total demand
            species_priority.sort(key=lambda x: (x[1], x[2]), reverse=True)
            
            # Create order quantities - be flexible about order sizes, especially for remaining demand
            total_remaining_demand = self.state.remaining_demand.sum().sum()
            is_final_phase = total_remaining_demand < VAN_CAPACITY * 3  # Less than 3 van loads remaining
            
            for species_id, polygon_need, total_demand in species_priority:
                if effective_space < 50:  # Need at least some space
                    break
                
                # Calculate order quantity - prioritize completing the project
                current_available = self.state.available_inventory[species_id]
                
                if is_final_phase:
                    # In final phase, order exactly what we need
                    needed = total_demand - current_available
                    if needed > 0:
                        order_qty = min(needed, effective_space)
                        min_order_size = 1  # Allow any order size in final phase
                    else:
                        continue  # Skip if we already have enough
                elif total_demand < VAN_CAPACITY * 2:
                    # If total demand is small, order exactly what we need
                    order_qty = min(total_demand, effective_space)
                    min_order_size = 50
                else:
                    # Otherwise order in van load increments
                    order_qty = min(
                        VAN_CAPACITY * 2,  # Prefer 2 van loads at a time
                        total_demand,
                        effective_space
                    )
                    min_order_size = VAN_CAPACITY // 2  # Normal minimum
                
                if order_qty >= min_order_size:
                    order_quantities.append((species_id, order_qty))
                    effective_space -= order_qty
                    if is_final_phase:
                        print(f"🔥 FINAL PHASE: Ordering {order_qty:,} of species {species_id} from {provider} (exactly what we need)")
                    else:
                        print(f"Planning to order {order_qty:,} of species {species_id} from {provider} (polygon need: {polygon_need}, total demand: {total_demand:,})")
            
            # Create order if we have quantities to order
            if order_quantities:
                total_plants = sum(qty for _, qty in order_quantities)
                
                # Don't exceed daily order limit
                if total_plants <= MAX_PLANTS_ORDER_PER_PROVIDER_PER_DAY:
                    order = Order(
                        order_day=self.state.current_day,
                        arrival_day=self.state.current_day + 1,
                        amount_of_plants=total_plants,
                        provider=provider,
                        species_id_quantity=order_quantities,
                        cost=0
                    )
                    
                    # Calculate order cost
                    order.cost = calculate_order_cost(order)
                    
                    if order.cost > 0:  # Only proceed if cost calculation was successful
                        # Add to orders list and update total cost
                        self.state.orders.append(order)
                        self.state.total_cost += order.cost
                        
                        # Update warehouse inventory for next day (stage 0)
                        for species_id, quantity in order_quantities:
                            self.state.acclim_stage_0[species_id] += quantity
                        
                        print(f"Ordered {total_plants:,} plants from {provider} (primary provider for day {self.state.current_day})")
                        print(f"Species: {', '.join(f'{s}:{q:,}' for s, q in order_quantities)}")
                        print(f"Order cost: ${order.cost:,.2f}")
                        
                        order_created = True
                    else:
                        print(f"Failed to calculate cost for order from {provider}")
        
        if not order_created:
            print(f"No orders were created this iteration (primary provider: {primary_provider})")
            # Debug: print current inventory levels
            print("Current available inventory:")
            for i in range(1, 11):
                available = self.state.available_inventory[i]
                total_demand = self.state.remaining_demand[i].sum()
                polygon_need = polygon_demand[i] if polygon_id else 0
                print(f"  Species {i}: {available:,} available, {total_demand:,} total demand, {polygon_need:,} needed in polygon {polygon_id}")
        
        return order_created
    
    def _plant_available_plants(self) -> bool:
        """Try to plant available plants. Returns True if any plants were planted."""
        plants_planted = False
        
        # Get next polygon to plant
        polygon_id = self._get_next_polygon()
        if polygon_id is None:
            print("No polygons with remaining demand")
            return False
        
        # Calculate maximum plants we can plant in this polygon today
        max_plants_per_day = self._calculate_max_plants_per_day(polygon_id)
        
        # Get demand for this polygon
        polygon_demand = self.state.remaining_demand.loc[polygon_id]
        
        # Find species that we can actually plant (have both inventory and demand)
        species_to_plant = []
        total_plants_to_plant = 0
        
        for species_id in range(1, 11):
            available = self.state.available_inventory[species_id]
            demand = polygon_demand[species_id]
            
            if demand > 0 and available > 0:
                # Plant as much as we can of this species (up to demand and available inventory)
                plants_to_plant = min(available, demand)
                species_to_plant.append((species_id, plants_to_plant))
                total_plants_to_plant += plants_to_plant
                print(f"Species {species_id}: planning to plant {plants_to_plant:,} (available: {available:,}, demand: {demand:,})")
        
        if not species_to_plant:
            print("No plantable species (no species with both inventory and demand)")
            return False
        
        # Limit by daily capacity - scale down proportionally if needed
        if total_plants_to_plant > max_plants_per_day:
            scale_factor = max_plants_per_day / total_plants_to_plant
            species_to_plant = [
                (species_id, int(plants * scale_factor))
                for species_id, plants in species_to_plant
            ]
            total_plants_to_plant = sum(plants for _, plants in species_to_plant)
            print(f"Scaled down to daily capacity: {total_plants_to_plant:,} plants")
        
        # Only proceed if we have a meaningful amount to plant
        # Be more flexible for small remaining quantities that could complete species
        min_worthwhile_plants = max(50, VAN_CAPACITY // 10)  # At least 50 plants or 1/10 van load
        
        # But be very aggressive if we're near completion
        total_remaining_demand = self.state.remaining_demand.sum().sum()
        if total_remaining_demand < VAN_CAPACITY * 5:  # Less than 5 van loads remaining total
            min_worthwhile_plants = 10  # Plant even very small quantities
        
        # Allow smaller quantities if they would complete a species in this polygon
        allow_small_completion = False
        for species_id, plants_to_plant in species_to_plant:
            remaining_after_planting = polygon_demand[species_id] - plants_to_plant
            if remaining_after_planting == 0:  # This would complete the species
                allow_small_completion = True
                break
        
        if total_plants_to_plant < min_worthwhile_plants and not allow_small_completion:
            print(f"Not enough plants to make worthwhile trip: {total_plants_to_plant} < {min_worthwhile_plants}")
            return False
        
        # Check labor time
        travel_time = self.time_matrix.loc[BASE_ID, polygon_id]
        return_time = self.time_matrix.loc[polygon_id, BASE_ID]
        trips_needed = (total_plants_to_plant + VAN_CAPACITY - 1) // VAN_CAPACITY
        total_trip_time = trips_needed * (travel_time + return_time + 1.0)
        
        if self.state.remaining_labor_hours < total_trip_time:
            print(f"Not enough labor hours: {self.state.remaining_labor_hours:.2f} < {total_trip_time:.2f}")
            return False
        
        print(f"Planning to plant {total_plants_to_plant:,} plants across {len(species_to_plant)} species")
        print(f"Need {trips_needed} trips, total time: {total_trip_time:.2f}h")
        
        # Calculate maximum treatment time needed for all species being planted
        max_treatment_time = max(get_treatment_time(species_id, 1) for species_id, _ in species_to_plant)
        print(f"Treatment time required: {max_treatment_time:.2f}h (max among all species)")
        
        # Plant each species
        for species_id, plants_of_this_species in species_to_plant:
            if plants_of_this_species > 0:
                # Create transportation activity
                transport = TransportationActivity(
                    day=self.state.current_day,
                    from_polygon=BASE_ID,
                    to_polygon=polygon_id,
                    species_id=species_id,
                    quantity=plants_of_this_species,
                    travel_time=travel_time * (plants_of_this_species / total_plants_to_plant),
                    load_time=0.5 * (plants_of_this_species / total_plants_to_plant),
                    unload_time=0.5 * (plants_of_this_species / total_plants_to_plant),
                    transport_cost=0
                )
                
                # Create planting activity - show individual treatment time for each species (for display)
                # The actual labor time calculation will only count max_treatment_time once
                individual_treatment_time = get_treatment_time(species_id, 1)
                
                planting = PlantingActivity(
                    day=self.state.current_day,
                    polygon_id=polygon_id,
                    species_id=species_id,
                    quantity=plants_of_this_species,
                    treatment_time=individual_treatment_time,
                    planting_cost=calculate_planting_cost(plants_of_this_species)
                )
                
                # Update state
                self.state.available_inventory[species_id] -= plants_of_this_species
                self.state.remaining_demand.loc[polygon_id, species_id] -= plants_of_this_species
                self.state.transportation_activities.append(transport)
                self.state.planting_activities.append(planting)
                self.state.total_cost += planting.planting_cost
                
                plants_planted = True
                print(f"Planted {plants_of_this_species:,} plants of species {species_id} (treatment: {individual_treatment_time:.2f}h)")
        
        # Update labor hours - use max treatment time only once, plus trip time
        total_labor_time = total_trip_time + max_treatment_time
        self.state.remaining_labor_hours -= total_labor_time
        
        if plants_planted:
            print(f"Successfully planted {total_plants_to_plant:,} plants in polygon {polygon_id}")
            print(f"Remaining labor: {self.state.remaining_labor_hours:.2f}h")
            
            # Check if polygon is complete
            remaining_demand_in_polygon = self.state.remaining_demand.loc[polygon_id].sum()
            if remaining_demand_in_polygon == 0:
                print(f"🎉 Polygon {polygon_id} is now COMPLETE!")
            else:
                print(f"Polygon {polygon_id} still needs {remaining_demand_in_polygon:,} more plants")
        else:
            print("No plants were planted this iteration")
        
        return plants_planted