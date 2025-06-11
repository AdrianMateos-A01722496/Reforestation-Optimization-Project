"""
Mathematical Optimization Model for Reforestation Supply Chain
More flexible constraints to ensure feasibility
"""

import pulp
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import json
from datetime import datetime, timedelta

# Import constants from utils
from utils import (
    PLANTATION_COST_PER_PLANT, VAN_CAPACITY, WAREHOUSE_CAPACITY,
    MAX_PLANTS_ORDER_PER_PROVIDER_PER_DAY, TRANSPORT_COST_PER_PLANT,
    LABOR_TIME, MIN_ACCLIMATION_DAYS, BASE_ID, PROVIDER_COSTS,
    SPECIES_PROPORTIONS, get_treatment_time
)

class RelaxedMathematicalOptimizer:
    def __init__(self, time_limit_days: int = 90):
        self.time_limit_days = time_limit_days
        self.selected_polygons = [24, 17, 15, 23, 14]  # 5 closest polygons to base 18
        self.species = list(range(1, 11))  # All 10 species
        self.providers = list(PROVIDER_COSTS.keys())
        self.days = list(range(1, time_limit_days + 1))
        
        # Load simplified data
        self.demand_data = self._load_simplified_demand()
        self.travel_times = self._load_simplified_travel_times()
        
        # Create the optimization model
        self.model = pulp.LpProblem("Relaxed_Reforestation_Optimization", pulp.LpMinimize)
        
        # Decision variables
        self._create_decision_variables()
        
        # Constraints
        self._add_relaxed_constraints()
        
        # Objective function
        self._set_objective()
    
    def _load_simplified_demand(self) -> Dict[Tuple[int, int], int]:
        """Load demand data for selected 5 polygons"""
        demand_df = pd.read_csv('data/encoded_demand.csv', index_col=0)
        demand_dict = {}
        
        for polygon in self.selected_polygons:
            for species in self.species:
                demand_dict[(polygon, species)] = int(demand_df.loc[polygon, str(species)])
        
        return demand_dict
    
    def _load_simplified_travel_times(self) -> Dict[Tuple[int, int], float]:
        """Load travel times from base (18) to selected polygons"""
        travel_df = pd.read_csv('data/tiempos.csv', index_col=0)
        travel_dict = {}
        
        for polygon in self.selected_polygons:
            # Travel time from base (18) to polygon
            travel_dict[(BASE_ID, polygon)] = float(travel_df.loc[BASE_ID, str(polygon)])
            # Travel time from polygon back to base
            travel_dict[(polygon, BASE_ID)] = float(travel_df.loc[polygon, str(BASE_ID)])
        
        return travel_dict
    
    def _create_decision_variables(self):
        """Create all decision variables for the optimization model"""
        
        # 1. Ordering variables: order[provider, species, day] = quantity
        self.order_vars = {}
        for provider in self.providers:
            for species in self.species:
                if species in PROVIDER_COSTS[provider]:  # Only species available from provider
                    for day in self.days:
                        var_name = f"order_{provider}_{species}_{day}"
                        self.order_vars[(provider, species, day)] = pulp.LpVariable(
                            var_name, lowBound=0, cat='Integer'
                        )
        
        # 2. Planting variables: plant[polygon, species, day] = quantity
        self.plant_vars = {}
        for polygon in self.selected_polygons:
            for species in self.species:
                for day in self.days:
                    var_name = f"plant_{polygon}_{species}_{day}"
                    self.plant_vars[(polygon, species, day)] = pulp.LpVariable(
                        var_name, lowBound=0, cat='Integer'
                    )
        
        # 3. Inventory variables: inventory[species, day] = quantity
        self.inventory_vars = {}
        for species in self.species:
            for day in range(0, self.time_limit_days + 1):  # Day 0 = initial
                var_name = f"inventory_{species}_{day}"
                self.inventory_vars[(species, day)] = pulp.LpVariable(
                    var_name, lowBound=0, cat='Integer'
                )
    
    def _add_relaxed_constraints(self):
        """Add relaxed constraints to improve feasibility"""
        
        # 1. Demand satisfaction constraints (must be met)
        for polygon in self.selected_polygons:
            for species in self.species:
                total_planted = pulp.lpSum([
                    self.plant_vars[(polygon, species, day)] 
                    for day in self.days
                ])
                self.model += (
                    total_planted >= self.demand_data[(polygon, species)],
                    f"demand_{polygon}_{species}"
                )
        
        # 2. Simplified inventory balance constraints
        for species in self.species:
            # Initial inventory is 0
            self.model += (
                self.inventory_vars[(species, 0)] == 0,
                f"initial_inventory_{species}"
            )
            
            for day in self.days:
                # Inventory balance equation (with relaxed acclimation)
                inventory_in = pulp.lpSum([
                    self.order_vars.get((provider, species, max(1, day - MIN_ACCLIMATION_DAYS)), 0)
                    for provider in self.providers
                    if (provider, species, max(1, day - MIN_ACCLIMATION_DAYS)) in self.order_vars
                ])
                
                inventory_out = pulp.lpSum([
                    self.plant_vars[(polygon, species, day)]
                    for polygon in self.selected_polygons
                ])
                
                self.model += (
                    self.inventory_vars[(species, day)] == 
                    self.inventory_vars[(species, day - 1)] + inventory_in - inventory_out,
                    f"inventory_balance_{species}_{day}"
                )
        
        # 3. Relaxed warehouse capacity
        for day in self.days:
            total_inventory = pulp.lpSum([
                self.inventory_vars[(species, day)]
                for species in self.species
            ])
            self.model += (
                total_inventory <= WAREHOUSE_CAPACITY * 1.2,  # 20% overflow allowed
                f"warehouse_capacity_{day}"
            )
        
        # 4. Relaxed ordering constraints
        for day in self.days:
            total_ordered = pulp.lpSum([
                self.order_vars[(provider, species, day)]
                for provider in self.providers
                for species in self.species
                if (provider, species, day) in self.order_vars
            ])
            
            # Allow multiple smaller orders per day
            self.model += (
                total_ordered <= MAX_PLANTS_ORDER_PER_PROVIDER_PER_DAY * 1.5,  # 50% more flexibility
                f"order_limit_{day}"
            )
        
        # 5. Simplified work day constraints
        for day in self.days:
            # Skip weekends (but relax this too)
            weekend_penalty = 2.0 if (day - 1) % 7 in [5, 6] else 1.0
            
            # Simplified capacity constraint per polygon per day
            for polygon in self.selected_polygons:
                total_plants_to_polygon = pulp.lpSum([
                    self.plant_vars[(polygon, species, day)]
                    for species in self.species
                ])
                
                # Allow more flexibility on van capacity
                self.model += (
                    total_plants_to_polygon <= VAN_CAPACITY * 2 / weekend_penalty,  # Up to 2 trips per day
                    f"daily_capacity_{polygon}_{day}"
                )
        
        # 6. Very simplified labor constraint (aggregate weekly)
        for week in range(0, self.time_limit_days // 7 + 1):
            week_start = week * 7 + 1
            week_end = min((week + 1) * 7, self.time_limit_days)
            
            total_weekly_plants = pulp.lpSum([
                self.plant_vars[(polygon, species, day)]
                for polygon in self.selected_polygons
                for species in self.species
                for day in range(week_start, week_end + 1)
                if day <= self.time_limit_days
            ])
            
            # Roughly 5 working days * 6 hours * capacity
            weekly_capacity = 5 * VAN_CAPACITY * 2  # Very generous
            self.model += (
                total_weekly_plants <= weekly_capacity,
                f"weekly_capacity_week_{week}"
            )
    
    def _set_objective(self):
        """Set the objective function to minimize total costs"""
        
        # 1. Plant ordering costs (including transport)
        ordering_cost = pulp.lpSum([
            self.order_vars[(provider, species, day)] * 
            (PROVIDER_COSTS[provider][species] + TRANSPORT_COST_PER_PLANT)
            for provider in self.providers
            for species in self.species
            for day in self.days
            if (provider, species, day) in self.order_vars
        ])
        
        # 2. Planting costs
        planting_cost = pulp.lpSum([
            self.plant_vars[(polygon, species, day)] * PLANTATION_COST_PER_PLANT
            for polygon in self.selected_polygons
            for species in self.species
            for day in self.days
        ])
        
        # 3. Small penalty for inventory holding (encourage just-in-time)
        inventory_cost = pulp.lpSum([
            self.inventory_vars[(species, day)] * 0.01  # $0.01 per plant per day
            for species in self.species
            for day in self.days
        ])
        
        # Total cost objective
        self.model += ordering_cost + planting_cost + inventory_cost
    
    def solve(self, solver_name: str = 'PULP_CBC_CMD', time_limit: int = 600) -> Dict:
        """Solve the optimization model"""
        
        print(f"Setting up solver with time limit: {time_limit} seconds")
        
        # Choose solver
        if solver_name == 'PULP_CBC_CMD':
            solver = pulp.PULP_CBC_CMD(timeLimit=time_limit)
        else:
            solver = None
        
        print("Starting optimization...")
        start_time = datetime.now()
        
        # Solve the model
        self.model.solve(solver)
        
        end_time = datetime.now()
        solve_time = (end_time - start_time).total_seconds()
        
        # Extract results
        status = pulp.LpStatus[self.model.status]
        objective_value = pulp.value(self.model.objective) if self.model.status == pulp.LpStatusOptimal else None
        
        print(f"Optimization completed in {solve_time:.2f} seconds")
        print(f"Status: {status}")
        if objective_value:
            print(f"Objective value: ${objective_value:,.2f}")
        
        # Extract solution details
        solution = self._extract_solution()
        
        return {
            'status': status,
            'objective_value': objective_value,
            'solve_time': solve_time,
            'solution': solution
        }
    
    def _extract_solution(self) -> Dict:
        """Extract the detailed solution from the optimization model"""
        
        if self.model.status != pulp.LpStatusOptimal:
            return {}
        
        solution = {
            'orders': [],
            'plantings': [],
            'inventory': {},
            'total_costs': {},
            'summary': {}
        }
        
        # Extract ordering decisions
        for (provider, species, day), var in self.order_vars.items():
            if var.varValue and var.varValue > 0:
                solution['orders'].append({
                    'day': day,
                    'provider': provider,
                    'species': species,
                    'quantity': int(var.varValue),
                    'cost': var.varValue * (PROVIDER_COSTS[provider][species] + TRANSPORT_COST_PER_PLANT)
                })
        
        # Extract planting decisions
        for (polygon, species, day), var in self.plant_vars.items():
            if var.varValue and var.varValue > 0:
                solution['plantings'].append({
                    'day': day,
                    'polygon': polygon,
                    'species': species,
                    'quantity': int(var.varValue),
                    'cost': var.varValue * PLANTATION_COST_PER_PLANT
                })
        
        # Extract inventory levels
        for (species, day), var in self.inventory_vars.items():
            if day not in solution['inventory']:
                solution['inventory'][day] = {}
            solution['inventory'][day][species] = int(var.varValue) if var.varValue else 0
        
        # Calculate cost breakdown
        total_ordering_cost = sum(order['cost'] for order in solution['orders'])
        total_planting_cost = sum(planting['cost'] for planting in solution['plantings'])
        
        solution['total_costs'] = {
            'ordering': total_ordering_cost,
            'planting': total_planting_cost,
            'total': total_ordering_cost + total_planting_cost
        }
        
        # Summary statistics
        solution['summary'] = {
            'total_orders': len(solution['orders']),
            'total_plantings': len(solution['plantings']),
            'total_plants_ordered': sum(order['quantity'] for order in solution['orders']),
            'total_plants_planted': sum(planting['quantity'] for planting in solution['plantings']),
            'last_order_day': max(order['day'] for order in solution['orders']) if solution['orders'] else 0,
            'last_planting_day': max(planting['day'] for planting in solution['plantings']) if solution['plantings'] else 0
        }
        
        return solution
    
    def print_solution_summary(self, result: Dict):
        """Print a summary of the optimization results"""
        
        if result['status'] != 'Optimal':
            print(f"❌ Optimization failed with status: {result['status']}")
            return
        
        solution = result['solution']
        summary = solution['summary']
        
        print("\n" + "="*60)
        print("🎯 RELAXED MATHEMATICAL OPTIMIZATION RESULTS")
        print("="*60)
        
        print(f"✅ Status: {result['status']}")
        print(f"💰 Total Cost: ${result['objective_value']:,.2f}")
        print(f"⏱️  Solve Time: {result['solve_time']:.2f} seconds")
        print(f"📅 Project Duration: {summary['last_planting_day']} days")
        
        print(f"\n📊 Cost Breakdown:")
        print(f"   Ordering: ${solution['total_costs']['ordering']:,.2f}")
        print(f"   Planting: ${solution['total_costs']['planting']:,.2f}")
        
        print(f"\n📦 Orders Summary:")
        print(f"   Total orders: {summary['total_orders']}")
        print(f"   Total plants ordered: {summary['total_plants_ordered']:,}")
        print(f"   Last order day: {summary['last_order_day']}")
        
        if solution['orders']:
            orders_by_provider = {}
            for order in solution['orders']:
                provider = order['provider']
                if provider not in orders_by_provider:
                    orders_by_provider[provider] = 0
                orders_by_provider[provider] += order['quantity']
            
            for provider, quantity in orders_by_provider.items():
                print(f"   {provider}: {quantity:,} plants")
        
        print(f"\n🌱 Planting Summary:")
        print(f"   Total plantings: {summary['total_plantings']}")
        print(f"   Total plants planted: {summary['total_plants_planted']:,}")
        print(f"   Last planting day: {summary['last_planting_day']}")
        
        if solution['plantings']:
            plantings_by_polygon = {}
            for planting in solution['plantings']:
                polygon = planting['polygon']
                if polygon not in plantings_by_polygon:
                    plantings_by_polygon[polygon] = 0
                plantings_by_polygon[polygon] += planting['quantity']
            
            for polygon, quantity in plantings_by_polygon.items():
                print(f"   Polygon {polygon}: {quantity:,} plants")
        
        print("\n" + "="*60)

def main():
    """Main function to run the relaxed mathematical optimization"""
    
    print("🚀 Starting Relaxed Mathematical Optimization Model")
    print("📍 Problem: Reforestation Supply Chain (5 closest polygons)")
    print("⏰ Time limit: 90 days")
    
    # Create and solve the optimization model
    optimizer = RelaxedMathematicalOptimizer(time_limit_days=90)
    
    print(f"\n📋 Problem Statistics:")
    print(f"   Polygons: {len(optimizer.selected_polygons)} {optimizer.selected_polygons}")
    print(f"   Species: {len(optimizer.species)}")
    print(f"   Providers: {len(optimizer.providers)}")
    print(f"   Time horizon: {optimizer.time_limit_days} days")
    print(f"   Total demand: {sum(optimizer.demand_data.values()):,} plants")
    
    # Solve with extended time limit
    result = optimizer.solve(solver_name='PULP_CBC_CMD', time_limit=600)  # 10 minutes
    
    # Print results
    optimizer.print_solution_summary(result)
    
    # Save results to file
    with open('mathematical_optimization_results.json', 'w') as f:
        # Convert numpy types to regular Python types for JSON serialization
        json_result = result.copy()
        if 'solution' in json_result and json_result['solution']:
            # Handle potential numpy types in the solution
            for key, value in json_result['solution'].items():
                if isinstance(value, dict):
                    json_result['solution'][key] = {str(k): v for k, v in value.items()}
        
        json.dump(json_result, f, indent=2, default=str)
    
    print(f"\n💾 Results saved to: mathematical_optimization_results.json")

if __name__ == "__main__":
    main()