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
    SPECIES_PROPORTIONS, WAREHOUSE_PROPORTIONS, OPTIMAL_PROVIDER_ALLOCATION,
    OPUNTIA_SPECIES_IDS
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
        max_days_without_progress = 30  # Allow more time for initial acclimation (was 20)
        last_demand = self.state.remaining_demand.sum().sum()
        
        while (not self.state.remaining_demand.empty and 
               self.state.remaining_demand.sum().sum() > 0 and
               self.state.current_day < max_days):
            
            current_demand = self.state.remaining_demand.sum().sum()
            current_inventory = self.state.get_total_warehouse_inventory()
            current_available = sum(self.state.available_inventory.values())
            
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
                    print(f"Available for planting: {current_available:,}")
                    
                    # Debug acclimation stages
                    print("Acclimation stages:")
                    print(f"  Stage 0 (arriving today): {sum(self.state.acclim_stage_0.values()):,}")
                    print(f"  Stage 1 (1 day old): {sum(self.state.acclim_stage_1.values()):,}")
                    print(f"  Stage 2 (2 days old): {sum(self.state.acclim_stage_2.values()):,}")
                    print(f"  Available (3+ days old): {current_available:,}")
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
                # WEEKDAY: AGGRESSIVE PLANTING - Always try to plant first!
                print(f"\n📅 WEEKDAY {self.state.current_day}: AGGRESSIVE PLANTING MODE")
                print(f"Current inventory: {current_inventory:,} plants")
                
                # Try to plant available plants first - be very aggressive
                planted_any = self._plant_available_plants()
                
                if not planted_any:
                    print("❌ No plants were planted today - analyzing why:")
                    polygon_id = self._get_next_polygon()
                    if polygon_id:
                        polygon_demand = self.state.remaining_demand.loc[polygon_id]
                        print(f"Next polygon {polygon_id} demand: {polygon_demand.sum():,} plants")
                        print("Available inventory by species:")
                        for i in range(1, 11):
                            available = self.state.available_inventory[i]
                            demand = polygon_demand[i]
                            print(f"  Species {i}: {available:,} available, {demand:,} needed")
                else:
                    print("✅ Successfully planted plants today!")
                
                # Always try to order more (if we have labor time or couldn't plant)
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
    
    def _get_next_polygon(self, exclude_polygons: set = None) -> int:
        """Get the next polygon to plant, prioritizing polygons that need available species"""
        if exclude_polygons is None:
            exclude_polygons = set()
            
        # Get all polygons with remaining demand
        polygon_demand_totals = self.state.remaining_demand.sum(axis=1)
        viable_polygons = polygon_demand_totals[polygon_demand_totals > 0].index.tolist()
        
        if not viable_polygons:
            return None
        
        # Remove warehouse polygon and excluded polygons
        viable_polygons = [p for p in viable_polygons if p != BASE_ID and p not in exclude_polygons]
        
        if not viable_polygons:
            return None
        
        # SMART SELECTION: Prioritize polygons that need species we actually have available
        available_species = [s for s in range(1, 11) if self.state.available_inventory[s] > 0]
        
        if available_species:
            print(f"🎯 Available species for planting: {available_species}")
            
            # Score polygons based on how many available species they need
            polygon_scores = []
            for polygon_id in viable_polygons:
                polygon_demand = self.state.remaining_demand.loc[polygon_id]
                
                # Count how many available species this polygon needs
                matching_species = 0
                total_matching_demand = 0
                
                for species_id in available_species:
                    if polygon_demand[species_id] > 0:
                        matching_species += 1
                        total_matching_demand += polygon_demand[species_id]
                
                polygon_scores.append((polygon_id, matching_species, total_matching_demand, polygon_demand_totals[polygon_id]))
                
            # Sort by: 1) Most matching species, 2) Highest matching demand, 3) Highest total demand
            polygon_scores.sort(key=lambda x: (x[1], x[2], x[3]), reverse=True)
            
            if polygon_scores:
                selected_polygon = polygon_scores[0][0]
                matching_count = polygon_scores[0][1]
                print(f"🏆 Selected polygon {selected_polygon} (matches {matching_count} available species)")
                return selected_polygon
        
        # Fallback: return polygon with highest total demand (excluding failed ones)
        viable_totals = {p: polygon_demand_totals[p] for p in viable_polygons}
        if viable_totals:
            max_demand_polygon = max(viable_totals.keys(), key=lambda p: viable_totals[p])
            print(f"📍 Fallback: Selected polygon {max_demand_polygon} (highest demand: {viable_totals[max_demand_polygon]:,})")
            return max_demand_polygon
        
        return None
    
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
        """Hybrid ordering strategy: Fill warehouse initially, then just-in-time replacement"""
        # Check available warehouse space
        current_inventory = self.state.get_total_warehouse_inventory()
        available_space = WAREHOUSE_CAPACITY - current_inventory
        
        # Account for pending arrivals (plants arriving tomorrow and later)
        pending_arrivals = 0
        for order in self.state.orders:
            if order.arrival_day > self.state.current_day:
                pending_arrivals += order.amount_of_plants
        
        effective_space = available_space - pending_arrivals
        
        if effective_space <= 0:
            print(f"⚠️  No warehouse space available. Current: {current_inventory}, Pending: {pending_arrivals}, Capacity: {WAREHOUSE_CAPACITY}")
            return False
        
        print(f"📦 Warehouse status: {current_inventory:,}/{WAREHOUSE_CAPACITY:,} used, {effective_space:,} available space")
        
        # PHASE 1: INITIAL AGGRESSIVE STOCKING (First 3 days)
        if self.state.current_day <= 3:
            return self._initial_aggressive_ordering(effective_space)
        
        # PHASE 2: JUST-IN-TIME REPLACEMENT ORDERING
        else:
            return self._just_in_time_ordering(effective_space)
    
    def _initial_aggressive_ordering(self, effective_space: int) -> bool:
        """Phase 1: Fill warehouse to capacity with smart proportions"""
        print(f"📋 PHASE 1: INITIAL AGGRESSIVE STOCKING (Day {self.state.current_day})")
        
        # Calculate total demand across all species to determine proportions
        total_demand_by_species = {}
        for species_id in range(1, 11):
            total_demand_by_species[species_id] = self.state.remaining_demand[species_id].sum()
        
        total_overall_demand = sum(total_demand_by_species.values())
        
        # Calculate proportional ordering amounts based on overall demand
        order_amounts = {}
        max_order_size = min(effective_space, MAX_PLANTS_ORDER_PER_PROVIDER_PER_DAY)
        
        for species_id in range(1, 11):
            if total_overall_demand > 0:
                proportion = total_demand_by_species[species_id] / total_overall_demand
                order_amounts[species_id] = int(max_order_size * proportion)
            else:
                order_amounts[species_id] = 0
        
        print(f"🎯 Proportional ordering for {max_order_size:,} plants:")
        for species_id, amount in order_amounts.items():
            if amount > 0:
                print(f"  Species {species_id}: {amount:,} plants ({amount/max_order_size*100:.1f}%)")
        
        # Select provider using rotation
        providers = ['laguna_seca', 'venado', 'moctezuma']
        primary_provider = providers[self.state.current_day % 3]
        
        # Try each provider in rotation order
        provider_order = [primary_provider] + [p for p in providers if p != primary_provider]
        
        for provider in provider_order:
            # Get species this provider should supply
            provider_species = OPTIMAL_PROVIDER_ALLOCATION.get(provider, [])
            
            # Create order for species this provider supplies
            order_quantities = []
            
            for species_id in provider_species:
                amount = order_amounts.get(species_id, 0)
                if amount > 0:
                    order_quantities.append((species_id, amount))
                    print(f"📝 Ordering {amount:,} of species {species_id} from {provider}")
            
            # Create order if we have quantities
            if order_quantities:
                total_plants = sum(qty for _, qty in order_quantities)
                
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
                
                if order.cost > 0:
                    # Add to orders and update cost
                    self.state.orders.append(order)
                    self.state.total_cost += order.cost
                    
                    # Update warehouse inventory for next day (stage 0)
                    for species_id, quantity in order_quantities:
                        self.state.acclim_stage_0[species_id] += quantity
                    
                    print(f"✅ BULK ORDER: {total_plants:,} plants from {provider} for ${order.cost:,.2f}")
                    print(f"   Species breakdown: {', '.join(f'{s}:{q:,}' for s, q in order_quantities)}")
                    return True
                else:
                    print(f"❌ Failed to calculate cost for order from {provider}")
        
        print("❌ No bulk orders could be created")
        return False
    
    def _just_in_time_ordering(self, effective_space: int) -> bool:
        """Phase 2: Just-in-time replacement ordering"""
        print(f"📋 PHASE 2: JUST-IN-TIME REPLACEMENT ORDERING")
        
        # Calculate what we'll need for tomorrow's planting + small buffer
        species_to_order = {}
        total_plants_needed = 0
        
        # Look at next polygon to plant and estimate daily consumption
        polygon_id = self._get_next_polygon()
        if polygon_id:
            max_daily_consumption = self._calculate_max_plants_per_day(polygon_id)
            # Conservative estimate: use 30% of max daily capacity as expected consumption
            expected_daily_consumption = max(200, max_daily_consumption // 3)
        else:
            expected_daily_consumption = 500  # Default fallback
        
        for species_id in range(1, 11):
            # Get current total inventory (all stages)
            current_species_inventory = (
                self.state.available_inventory[species_id] +
                self.state.acclim_stage_0[species_id] +
                self.state.acclim_stage_1[species_id] +
                self.state.acclim_stage_2[species_id]
            )
            
            # Get total remaining demand
            total_species_demand = self.state.remaining_demand[species_id].sum()
            
            if total_species_demand == 0:
                continue
            
            # Calculate species proportion of total demand
            total_demand = self.state.remaining_demand.sum().sum()
            if total_demand > 0:
                species_proportion = total_species_demand / total_demand
                expected_species_consumption = int(expected_daily_consumption * species_proportion)
                
                # Order if inventory will be low (less than 2 days of consumption)
                safety_threshold = max(50, expected_species_consumption * 2)
                
                if current_species_inventory < safety_threshold:
                    # Order enough for ~3 days of consumption
                    order_amount = max(expected_species_consumption * 3, 100)
                    # Don't order more than remaining demand
                    order_amount = min(order_amount, total_species_demand)
                    
                    species_to_order[species_id] = order_amount
                    total_plants_needed += order_amount
                    print(f"🔄 Species {species_id}: Need {order_amount:,} (have: {current_species_inventory:,}, daily consumption: ~{expected_species_consumption:,})")
                else:
                    print(f"✅ Species {species_id}: Sufficient inventory ({current_species_inventory:,} have, threshold: {safety_threshold:,})")
        
        if not species_to_order:
            print("✅ All species have sufficient inventory for near-term planting!")
            return False
        
        # Limit order to available warehouse space
        max_order_size = min(effective_space, total_plants_needed, MAX_PLANTS_ORDER_PER_PROVIDER_PER_DAY)
        
        if max_order_size <= 0:
            print(f"⚠️  Cannot order: warehouse space too limited ({effective_space:,} available)")
            return False
        
        print(f"🎯 Just-in-time order needed: {total_plants_needed:,}, Max order size: {max_order_size:,}")
        
        # Select provider using rotation
        providers = ['laguna_seca', 'venado', 'moctezuma']
        primary_provider = providers[self.state.current_day % 3]
        
        # Try each provider in rotation order
        provider_order = [primary_provider] + [p for p in providers if p != primary_provider]
        
        for provider in provider_order:
            # Get species this provider should supply
            provider_species = OPTIMAL_PROVIDER_ALLOCATION.get(provider, [])
            
            # Find species we need that this provider can supply
            order_quantities = []
            remaining_order_space = max_order_size
            
            # Prioritize species we need most urgently
            provider_needs = []
            for species_id in provider_species:
                if species_id in species_to_order and remaining_order_space > 0:
                    needed = min(species_to_order[species_id], remaining_order_space)
                    if needed > 0:
                        provider_needs.append((species_id, needed))
            
            # Sort by need (descending) 
            provider_needs.sort(key=lambda x: x[1], reverse=True)
            
            for species_id, needed in provider_needs:
                if remaining_order_space <= 0:
                    break
                    
                order_qty = min(needed, remaining_order_space)
                order_quantities.append((species_id, order_qty))
                remaining_order_space -= order_qty
                print(f"📝 JIT ordering {order_qty:,} of species {species_id} from {provider}")
            
            # Create order if we have quantities
            if order_quantities:
                total_plants = sum(qty for _, qty in order_quantities)
                
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
                
                if order.cost > 0:
                    # Add to orders and update cost
                    self.state.orders.append(order)
                    self.state.total_cost += order.cost
                    
                    # Update warehouse inventory for next day (stage 0)
                    for species_id, quantity in order_quantities:
                        self.state.acclim_stage_0[species_id] += quantity
                    
                    print(f"✅ JIT ORDER: {total_plants:,} plants from {provider} for ${order.cost:,.2f}")
                    print(f"   Species breakdown: {', '.join(f'{s}:{q:,}' for s, q in order_quantities)}")
                    return True
                else:
                    print(f"❌ Failed to calculate cost for order from {provider}")
        
        print("❌ No JIT orders could be created")
        return False
    
    def _plant_available_plants(self) -> bool:
        """MULTI-TRIP BEAST: Maximize trips per day using short travel times"""
        plants_planted = False
        total_trips = 0
        failed_polygons = set()  # Track polygons that failed to prevent infinite loops
        
        print(f"\n🚀 MULTI-TRIP OPTIMIZATION: Starting with {self.state.remaining_labor_hours:.2f}h")
        
        # AGGRESSIVE MULTI-TRIP STRATEGY: Keep going until labor exhausted
        while self.state.remaining_labor_hours > 1.0:  # Need at least 1h for minimum trip
            trip_made = False
            
            # Get next polygon to plant (excluding failed polygons)
            polygon_id = self._get_next_polygon(exclude_polygons=failed_polygons)
            if polygon_id is None:
                print("No polygons with remaining demand (excluding failed polygons)")
                break
            
            # Calculate trip logistics
            travel_time = self.time_matrix.loc[BASE_ID, polygon_id]
            return_time = self.time_matrix.loc[polygon_id, BASE_ID]
            polygon_demand = self.state.remaining_demand.loc[polygon_id]
            max_plants_per_day = self._calculate_max_plants_per_day(polygon_id)
            
            print(f"\n🎯 TRIP ATTEMPT #{total_trips + 1} to Polygon {polygon_id}")
            print(f"   Travel: {travel_time:.3f}h each way, Labor remaining: {self.state.remaining_labor_hours:.2f}h")
            
            # PRIORITY 1: SCALED OPUNTIA TRIPS (maximize truck efficiency)
            if self._try_scaled_opuntia_trip(polygon_id, polygon_demand, travel_time, return_time, max_plants_per_day, total_trips + 1):
                total_trips += 1
                plants_planted = True
                trip_made = True
                print(f"✅ SCALED OPUNTIA TRIP #{total_trips} completed!")
                # Remove from failed list since it succeeded
                failed_polygons.discard(polygon_id)
                continue
            
            # PRIORITY 2: SCALED NON-OPUNTIA TRIPS (maximize truck efficiency)
            if self._try_scaled_non_opuntia_trip(polygon_id, polygon_demand, travel_time, return_time, max_plants_per_day, total_trips + 1):
                total_trips += 1
                plants_planted = True
                trip_made = True
                print(f"✅ SCALED NON-OPUNTIA TRIP #{total_trips} completed!")
                failed_polygons.discard(polygon_id)
                continue
            
            # PRIORITY 3: EFFICIENT MIXED TRIPS (plant multiple species efficiently)
            mixed_trip_result = self._try_efficient_mixed_trip(polygon_id, polygon_demand, travel_time, return_time, max_plants_per_day, total_trips + 1)
            if mixed_trip_result:
                total_trips += 1
                plants_planted = True
                trip_made = True
                print(f"✅ MIXED TRIP #{total_trips} completed!")
                failed_polygons.discard(polygon_id)
                continue
            
            # PRIORITY 4: SINGLE SPECIES TRIPS (use remaining time efficiently)
            single_trip_result = self._try_single_species_trip(polygon_id, polygon_demand, travel_time, return_time, total_trips + 1)
            if single_trip_result:
                total_trips += 1
                plants_planted = True
                trip_made = True
                print(f"✅ SINGLE SPECIES TRIP #{total_trips} completed!")
                failed_polygons.discard(polygon_id)
                continue
            
            # If no trip was possible with this polygon, mark it as failed
            if not trip_made:
                print(f"❌ No viable trip to polygon {polygon_id}")
                failed_polygons.add(polygon_id)
                
                # Check if all viable polygons have failed
                viable_polygons = self.state.remaining_demand.sum(axis=1)
                viable_polygons = viable_polygons[viable_polygons > 0].index.tolist()
                viable_polygons = [p for p in viable_polygons if p != BASE_ID]  # Remove warehouse
                
                remaining_polygons = set(viable_polygons) - failed_polygons
                
                if not remaining_polygons:
                    print(f"🔴 All viable polygons have failed with current inventory")
                    print(f"   Failed polygons: {sorted(failed_polygons)}")
                    print(f"   Available inventory: {[f'{i}:{self.state.available_inventory[i]}' for i in range(1,11) if self.state.available_inventory[i] > 0]}")
                    break
                
                print(f"   Polygon {polygon_id} added to failed list (total failed: {len(failed_polygons)})")
                continue
        
        if plants_planted:
            print(f"\n🏆 MULTI-TRIP SUMMARY:")
            print(f"   🚛 Total trips completed: {total_trips}")
            print(f"   ⏰ Labor hours remaining: {self.state.remaining_labor_hours:.2f}h")
            print(f"   📦 Warehouse status: {self.state.get_total_warehouse_inventory():,}/10,000")
        else:
            print(f"\n❌ NO TRIPS COMPLETED:")
            print(f"   Failed polygons: {sorted(failed_polygons) if failed_polygons else 'None'}")
            print(f"   Labor remaining: {self.state.remaining_labor_hours:.2f}h")
            print(f"   Available inventory: {[f'{i}:{self.state.available_inventory[i]}' for i in range(1,11) if self.state.available_inventory[i] > 0]}")
        
        return plants_planted
    
    def _try_scaled_opuntia_trip(self, polygon_id: int, polygon_demand, travel_time: float, return_time: float, max_plants_per_day: int, trip_number: int) -> bool:
        """Try to plant a scaled opuntia trip (species 5,6,7,8 with 20 min treatment)"""
        # Opuntia proportions per hectare: {5: 39, 6: 30, 7: 58, 8: 51} = 178 total
        # Scale to 524 truck capacity: 524/178 = 2.94x
        # Scaled: {5: 115, 6: 88, 7: 170, 8: 150} = 523 plants
        
        opuntia_proportions = {5: 39, 6: 30, 7: 58, 8: 51}
        total_opuntia_per_hectare = sum(opuntia_proportions.values())  # 178
        scale_factor = VAN_CAPACITY / total_opuntia_per_hectare  # 2.94
        
        scaled_opuntia_requirements = {
            species_id: int(proportion * scale_factor)
            for species_id, proportion in opuntia_proportions.items()
        }
        
        # Check if we have enough inventory and demand for a scaled opuntia trip
        can_do_scaled_trip = True
        for species_id, required in scaled_opuntia_requirements.items():
            available = self.state.available_inventory[species_id]
            demand = polygon_demand[species_id]
            
            if available < required or demand < required:
                can_do_scaled_trip = False
                break
        
        if not can_do_scaled_trip:
            return False
        
        # Calculate trip requirements
        total_plants = sum(scaled_opuntia_requirements.values())
        trip_time = travel_time + return_time + 1.0  # Include load/unload
        treatment_time = get_treatment_time(5, 1)  # 0.33 hours for opuntias
        total_time = trip_time + treatment_time
        
        if self.state.remaining_labor_hours < total_time or total_plants > max_plants_per_day:
            return False
        
        print(f"🌵 SCALED OPUNTIA TRIP: {total_plants} plants (species 5,6,7,8)")
        
        # Execute the trip
        for species_id, quantity in scaled_opuntia_requirements.items():
            self._execute_planting(polygon_id, species_id, quantity, travel_time, treatment_time, trip_number)
        
        # Update labor hours
        self.state.remaining_labor_hours -= total_time
        print(f"Opuntia trip completed. Remaining labor: {self.state.remaining_labor_hours:.2f}h")
        
        return True
    
    def _try_scaled_non_opuntia_trip(self, polygon_id: int, polygon_demand, travel_time: float, return_time: float, max_plants_per_day: int, trip_number: int) -> bool:
        """Try to plant a scaled non-opuntia trip (species 1,2,3,4,9,10 with 1 hour treatment)"""
        # Non-opuntia proportions per hectare: {1: 33, 2: 157, 3: 33, 4: 33, 9: 69, 10: 21} = 346 total
        # Scale to 524 truck capacity: 524/346 = 1.51x
        # Scaled: {1: 50, 2: 237, 3: 50, 4: 50, 9: 104, 10: 32} = 523 plants
        
        non_opuntia_proportions = {1: 33, 2: 157, 3: 33, 4: 33, 9: 69, 10: 21}
        total_non_opuntia_per_hectare = sum(non_opuntia_proportions.values())  # 346
        scale_factor = VAN_CAPACITY / total_non_opuntia_per_hectare  # 1.51
        
        scaled_non_opuntia_requirements = {
            species_id: int(proportion * scale_factor)
            for species_id, proportion in non_opuntia_proportions.items()
        }
        
        # Check if we have enough inventory and demand for a scaled non-opuntia trip
        can_do_scaled_trip = True
        for species_id, required in scaled_non_opuntia_requirements.items():
            available = self.state.available_inventory[species_id]
            demand = polygon_demand[species_id]
            
            if available < required or demand < required:
                can_do_scaled_trip = False
                break
        
        if not can_do_scaled_trip:
            return False
        
        # Calculate trip requirements
        total_plants = sum(scaled_non_opuntia_requirements.values())
        trip_time = travel_time + return_time + 1.0  # Include load/unload
        treatment_time = get_treatment_time(1, 1)  # 1 hour for non-opuntias
        total_time = trip_time + treatment_time
        
        if self.state.remaining_labor_hours < total_time or total_plants > max_plants_per_day:
            return False
        
        print(f"🌱 SCALED NON-OPUNTIA TRIP: {total_plants} plants (species 1,2,3,4,9,10)")
        
        # Execute the trip
        for species_id, quantity in scaled_non_opuntia_requirements.items():
            self._execute_planting(polygon_id, species_id, quantity, travel_time, treatment_time, trip_number)
        
        # Update labor hours
        self.state.remaining_labor_hours -= total_time
        print(f"Non-opuntia trip completed. Remaining labor: {self.state.remaining_labor_hours:.2f}h")
        
        return True
    
    def _try_efficient_mixed_trip(self, polygon_id: int, polygon_demand, travel_time: float, return_time: float, max_plants_per_day: int, trip_number: int) -> bool:
        """Try to plant a mixed trip that plants multiple species efficiently"""
        # Collect available plants by treatment type
        available_opuntias = {}
        available_non_opuntias = {}
        
        for species_id in range(1, 11):
            available = self.state.available_inventory[species_id]
            demand = polygon_demand[species_id]
            plantable = min(available, demand)
            
            if plantable > 0:
                if species_id in OPUNTIA_SPECIES_IDS:
                    available_opuntias[species_id] = plantable
                else:
                    available_non_opuntias[species_id] = plantable
        
        trips_completed = 0
        
        # Try opuntias first (shorter treatment time) - STRICT VAN CAPACITY
        opuntia_planted = False
        if available_opuntias:
            # Calculate total and enforce strict van capacity limit
            total_opuntias = sum(available_opuntias.values())
            
            # CRITICAL: Limit to VAN_CAPACITY for this single trip
            if total_opuntias > VAN_CAPACITY:
                scale_factor = VAN_CAPACITY / total_opuntias
                for species_id in available_opuntias:
                    available_opuntias[species_id] = int(available_opuntias[species_id] * scale_factor)
                total_opuntias = sum(available_opuntias.values())
            
            # Only proceed if we have plants and they fit in one van
            if total_opuntias >= 1 and total_opuntias <= VAN_CAPACITY:
                trip_time = travel_time + return_time + 1.0
                treatment_time = get_treatment_time(5, 1)  # 0.33 hours
                total_time = trip_time + treatment_time
                
                if self.state.remaining_labor_hours >= total_time:
                    opuntia_trip_number = trip_number + trips_completed
                    print(f"🌵 EFFICIENT OPUNTIA TRIP #{opuntia_trip_number}: {total_opuntias} plants (STRICT VAN CAPACITY)")
                    
                    # Execute all species in this single trip
                    for species_id, quantity in available_opuntias.items():
                        if quantity > 0:
                            self._execute_planting(polygon_id, species_id, quantity, travel_time, treatment_time, opuntia_trip_number)
                    
                    self.state.remaining_labor_hours -= total_time
                    print(f"Opuntia trip #{opuntia_trip_number} completed. Remaining labor: {self.state.remaining_labor_hours:.2f}h")
                    opuntia_planted = True
                    trips_completed += 1
        
        # Try non-opuntias if we still have labor time - SEPARATE TRIP WITH STRICT VAN CAPACITY
        non_opuntia_planted = False
        if self.state.remaining_labor_hours > 1.5 and available_non_opuntias:
            # Calculate total and enforce strict van capacity limit
            total_non_opuntias = sum(available_non_opuntias.values())
            
            # CRITICAL: Limit to VAN_CAPACITY for this single trip
            if total_non_opuntias > VAN_CAPACITY:
                scale_factor = VAN_CAPACITY / total_non_opuntias
                for species_id in available_non_opuntias:
                    available_non_opuntias[species_id] = int(available_non_opuntias[species_id] * scale_factor)
                total_non_opuntias = sum(available_non_opuntias.values())
            
            # Only proceed if we have plants and they fit in one van
            if total_non_opuntias >= 1 and total_non_opuntias <= VAN_CAPACITY:
                trip_time = travel_time + return_time + 1.0
                treatment_time = get_treatment_time(1, 1)  # 1 hour
                total_time = trip_time + treatment_time
                
                if self.state.remaining_labor_hours >= total_time:
                    non_opuntia_trip_number = trip_number + trips_completed
                    print(f"🌱 EFFICIENT NON-OPUNTIA TRIP #{non_opuntia_trip_number}: {total_non_opuntias} plants (STRICT VAN CAPACITY)")
                    
                    # Execute all species in this separate trip
                    for species_id, quantity in available_non_opuntias.items():
                        if quantity > 0:
                            self._execute_planting(polygon_id, species_id, quantity, travel_time, treatment_time, non_opuntia_trip_number)
                    
                    self.state.remaining_labor_hours -= total_time
                    print(f"Non-opuntia trip #{non_opuntia_trip_number} completed. Remaining labor: {self.state.remaining_labor_hours:.2f}h")
                    non_opuntia_planted = True
                    trips_completed += 1
        
        return opuntia_planted or non_opuntia_planted
    
    def _try_single_species_trip(self, polygon_id: int, polygon_demand, travel_time: float, return_time: float, trip_number: int) -> bool:
        """Try to plant a single species trip that uses remaining time efficiently"""
        # Find the species with the most available plants that has demand
        best_species = None
        max_plantable = 0
        best_treatment_time = 0
        
        for species_id in range(1, 11):
            available = self.state.available_inventory[species_id]
            demand = polygon_demand[species_id]
            plantable = min(available, demand)
            
            if plantable > max_plantable:
                max_plantable = plantable
                best_species = species_id
                best_treatment_time = get_treatment_time(species_id, 1)
        
        if best_species is None or max_plantable < 1:
            return False
        
        # Calculate trip time
        trip_time = travel_time + return_time + 1.0  # travel + load/unload
        total_time = trip_time + best_treatment_time
        
        if self.state.remaining_labor_hours < total_time:
            return False
        
        # Determine how many plants to take (up to truck capacity)
        plants_to_take = min(max_plantable, VAN_CAPACITY)
        
        print(f"🚛 SINGLE SPECIES TRIP: {plants_to_take} of species {best_species}")
        
        # Execute the trip
        self._execute_planting(polygon_id, best_species, plants_to_take, travel_time, best_treatment_time, trip_number)
        
        # Update labor hours
        self.state.remaining_labor_hours -= total_time
        print(f"Single species trip completed. Remaining labor: {self.state.remaining_labor_hours:.2f}h")
        
        return True
    
    def _execute_planting(self, polygon_id: int, species_id: int, quantity: int, travel_time: float, treatment_time: float, trip_number: int = 1):
        """Execute the actual planting of a species"""
        # Create transportation activity
        transport = TransportationActivity(
            day=self.state.current_day,
            from_polygon=BASE_ID,
            to_polygon=polygon_id,
            species_id=species_id,
            quantity=quantity,
            travel_time=travel_time,
            load_time=0.5,
            unload_time=0.5,
            transport_cost=0
        )
        
        # Create planting activity with trip number
        planting = PlantingActivity(
            day=self.state.current_day,
            polygon_id=polygon_id,
            species_id=species_id,
            quantity=quantity,
            treatment_time=treatment_time,
            planting_cost=calculate_planting_cost(quantity),
            trip_number=trip_number  # Add trip number to planting activity
        )
        
        # Update state
        self.state.available_inventory[species_id] -= quantity
        self.state.remaining_demand.loc[polygon_id, species_id] -= quantity
        self.state.transportation_activities.append(transport)
        self.state.planting_activities.append(planting)
        self.state.total_cost += planting.planting_cost
        
        print(f"  Trip {trip_number} - Species {species_id}: planted {quantity:,} plants")