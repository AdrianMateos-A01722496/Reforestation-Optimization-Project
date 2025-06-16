"""
Mathematical Optimization Model for Reforestation Supply Chain
Using PuLP for Linear Programming

This model optimizes the supply chain for a reforestation project involving:
- 10 plant species from 3 nursery providers
- 30 planting polygons + 1 warehouse (polygon 18)
- Inventory management with acclimatization periods
- Transport and operational constraints
"""

import pulp
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import constants and utilities
from utils import (
    VAN_CAPACITY, WAREHOUSE_CAPACITY, MAX_PLANTS_ORDER_PER_PROVIDER_PER_DAY,
    BASE_ID, LABOR_TIME, PLANTATION_COST_PER_PLANT, PROVIDER_COSTS, SPECIES_IDS,
    MIN_ACCLIMATION_DAYS, DEMAND_DF, TIME_DF, TRANSPORT_COST_PER_PLANT,
    ORDER_DELIVERY_TIME, LOAD_TIME_PER_PLANT, UNLOAD_TIME_PER_PLANT,
    NORMAL_TREATMENT_HR_PER_PLANT, OPUNTIA_TREATMENT_HR_PER_PLANT, OPUNTIA_SPECIES_IDS
)


class ReforestationOptimizer:
    """
    Mathematical optimization model for reforestation supply chain management.
    
    This class encapsulates the complete linear programming model including:
    - Decision variables
    - Objective function
    - All constraints from the mathematical formulation
    - Solution analysis and reporting
    """
    
    def __init__(self, 
                 selected_polygons: Optional[List[int]] = None,
                 time_horizon: int = 60,
                 objective_type: str = 'cost'):
        """
        Initialize the optimization model.
        
        Args:
            selected_polygons: List of polygon IDs to include (None for all)
            time_horizon: Number of days to optimize over
            objective_type: 'cost' or 'time' for optimization objective
        """
        self.time_horizon = time_horizon
        self.objective_type = objective_type
        
        # Define sets
        self.species = SPECIES_IDS
        self.providers = list(PROVIDER_COSTS.keys())
        self.all_polygons = list(range(1, 32))
        self.warehouse_id = BASE_ID
        
        # Select subset of planting polygons if specified
        if selected_polygons:
            self.planting_polygons = [p for p in selected_polygons if p != self.warehouse_id]
        else:
            self.planting_polygons = [p for p in self.all_polygons if p != self.warehouse_id]
            
        self.days = list(range(1, time_horizon + 1))
        self.acclimation_stages = list(range(MIN_ACCLIMATION_DAYS))
        
        # Filter demand data for selected polygons
        self.demand = DEMAND_DF.loc[self.planting_polygons].copy()
        
        # Treatment times by species (CONSTANT per species regardless of quantity)
        self.treatment_times = {
            e: OPUNTIA_TREATMENT_HR_PER_PLANT if e in OPUNTIA_SPECIES_IDS 
            else NORMAL_TREATMENT_HR_PER_PLANT 
            for e in self.species
        }
        
        # Work schedule (assuming Monday=1, Sunday=7)
        self.workdays = self._generate_workday_schedule()
        
        # Initialize model
        self.model = None
        self.variables = {}
        self.solution_status = None
        
        logger.info(f"Initialized optimizer for {len(self.planting_polygons)} polygons, "
                   f"{time_horizon} days, optimizing for {objective_type}")
    
    def _generate_workday_schedule(self) -> Dict[int, bool]:
        """Generate workday schedule (Mon-Fri = True, Sat-Sun = False)"""
        workdays = {}
        # Assume day 1 is Monday for simplicity
        for day in self.days:
            day_of_week = ((day - 1) % 7) + 1  # 1=Mon, 7=Sun
            workdays[day] = day_of_week <= 5  # Mon-Fri are workdays
        return workdays
    
    def _create_variables(self):
        """Create all decision variables for the optimization model."""
        logger.info("Creating decision variables...")
        
        # === CORE VARIABLES ===
        # Purchase variables
        self.variables['X'] = pulp.LpVariable.dicts(
            "Purchase",
            (self.species, self.providers, self.days),
            lowBound=0, cat='Integer'
        )
        
        # Order binary variables
        self.variables['Y'] = pulp.LpVariable.dicts(
            "OrderPlaced",
            (self.providers, self.days),
            cat='Binary'
        )
        
        # Inventory in acclimatization
        self.variables['InvAclim'] = pulp.LpVariable.dicts(
            "InventoryAcclimating",
            (self.species, self.acclimation_stages, self.days),
            lowBound=0, cat='Integer'
        )
        
        # Available inventory
        self.variables['InvDisp'] = pulp.LpVariable.dicts(
            "InventoryAvailable",
            (self.species, self.days),
            lowBound=0, cat='Integer'
        )
        
        # Shipments to polygons
        self.variables['S'] = pulp.LpVariable.dicts(
            "Shipment",
            (self.species, self.planting_polygons, self.days),
            lowBound=0, cat='Integer'
        )
        
        # Number of trips
        self.variables['N_trips'] = pulp.LpVariable.dicts(
            "NumberOfTrips",
            (self.planting_polygons, self.days),
            lowBound=0, cat='Integer'
        )
        
        # Plants planted
        self.variables['Planted'] = pulp.LpVariable.dicts(
            "Planted",
            (self.species, self.planting_polygons, self.days),
            lowBound=0, cat='Integer'
        )
        
        # === ADVANCED VARIABLES ===
        
        # 1. MULTI-VEHICLE FLEET VARIABLES
        # Simulate different vehicle configurations and routing decisions
        vehicle_types = ['standard', 'large', 'express']
        self.variables['VehicleUsed'] = pulp.LpVariable.dicts(
            "VehicleTypeUsed",
            (vehicle_types, self.planting_polygons, self.days),
            cat='Binary'
        )
        
        self.variables['VehicleCapacity'] = pulp.LpVariable.dicts(
            "VehicleCapacityUsed",
            (vehicle_types, self.planting_polygons, self.days),
            lowBound=0, cat='Integer'
        )
        
        # 2. DETAILED TIMING VARIABLES
        # Exact scheduling within days
        time_slots = list(range(24))  # Hourly time slots
        self.variables['TimeSlotUsed'] = pulp.LpVariable.dicts(
            "TimeSlotUsed",
            (self.planting_polygons, self.days, time_slots),
            cat='Binary'
        )
        
        self.variables['StartTime'] = pulp.LpVariable.dicts(
            "StartTime",
            (self.planting_polygons, self.days),
            lowBound=0, upBound=24, cat='Continuous'
        )
        
        self.variables['EndTime'] = pulp.LpVariable.dicts(
            "EndTime",
            (self.planting_polygons, self.days),
            lowBound=0, upBound=24, cat='Continuous'
        )
        
        # 3. WORKFORCE ALLOCATION VARIABLES
        worker_types = ['supervisor', 'planter', 'driver', 'specialist']
        self.variables['WorkerAssigned'] = pulp.LpVariable.dicts(
            "WorkerAssigned",
            (worker_types, self.planting_polygons, self.days),
            lowBound=0, cat='Integer'
        )
        
        self.variables['WorkerHours'] = pulp.LpVariable.dicts(
            "WorkerHours",
            (worker_types, self.planting_polygons, self.days),
            lowBound=0, cat='Continuous'
        )
        
        # 4. QUALITY AND ENVIRONMENTAL VARIABLES
        quality_levels = ['premium', 'standard', 'basic']
        self.variables['QualityLevel'] = pulp.LpVariable.dicts(
            "QualityLevel",
            (quality_levels, self.species, self.planting_polygons, self.days),
            cat='Binary'
        )
        
        weather_conditions = ['sunny', 'cloudy', 'rainy', 'windy']
        self.variables['WeatherAdjustment'] = pulp.LpVariable.dicts(
            "WeatherAdjustment",
            (weather_conditions, self.days),
            cat='Binary'
        )
        
        # 5. STORAGE ALLOCATION VARIABLES
        storage_zones = list(range(10))  # Multiple warehouse zones
        self.variables['StorageAllocation'] = pulp.LpVariable.dicts(
            "StorageAllocation",
            (self.species, storage_zones, self.days),
            lowBound=0, cat='Integer'
        )
        
        self.variables['ZoneActive'] = pulp.LpVariable.dicts(
            "ZoneActive",
            (storage_zones, self.days),
            cat='Binary'
        )
        
        # 6. SEQUENTIAL ORDERING VARIABLES
        order_sequences = list(range(5))  # Multiple order sequences per day
        self.variables['OrderSequence'] = pulp.LpVariable.dicts(
            "OrderSequence",
            (self.providers, order_sequences, self.days),
            cat='Binary'
        )
        
        self.variables['OrderPriority'] = pulp.LpVariable.dicts(
            "OrderPriority",
            (self.species, self.providers, self.days),
            lowBound=1, upBound=10, cat='Integer'
        )
        
        # 7. ROUTE OPTIMIZATION VARIABLES
        # Detailed routing between polygons
        self.variables['Route'] = pulp.LpVariable.dicts(
            "Route",
            (self.planting_polygons, self.planting_polygons, self.days),
            cat='Binary'
        )
        
        self.variables['RouteLoad'] = pulp.LpVariable.dicts(
            "RouteLoad",
            (self.planting_polygons, self.planting_polygons, self.days),
            lowBound=0, cat='Integer'
        )
        
        # 8. BATCH PROCESSING VARIABLES
        batch_sizes = [100, 200, 300, 524]  # Different batch sizes
        self.variables['BatchUsed'] = pulp.LpVariable.dicts(
            "BatchUsed",
            (batch_sizes, self.species, self.planting_polygons, self.days),
            cat='Binary'
        )
        
        self.variables['BatchCount'] = pulp.LpVariable.dicts(
            "BatchCount",
            (batch_sizes, self.species, self.planting_polygons, self.days),
            lowBound=0, cat='Integer'
        )
        
        # 9. SUSTAINABILITY METRICS VARIABLES
        sustainability_levels = ['eco_premium', 'eco_standard', 'conventional']
        self.variables['SustainabilityChoice'] = pulp.LpVariable.dicts(
            "SustainabilityChoice",
            (sustainability_levels, self.species, self.days),
            cat='Binary'
        )
        
        # 10. RISK MANAGEMENT VARIABLES
        risk_factors = ['weather_risk', 'supply_risk', 'quality_risk', 'timing_risk']
        self.variables['RiskMitigation'] = pulp.LpVariable.dicts(
            "RiskMitigation",
            (risk_factors, self.days),
            cat='Binary'
        )
        
        self.variables['ContingencyBuffer'] = pulp.LpVariable.dicts(
            "ContingencyBuffer",
            (self.species, self.days),
            lowBound=0, cat='Integer'
        )
        
        # 11. MULTI-OBJECTIVE VARIABLES
        self.variables['CostDeviation'] = pulp.LpVariable.dicts(
            "CostDeviation",
            (self.days,),
            lowBound=0, cat='Continuous'
        )
        
        self.variables['TimeDeviation'] = pulp.LpVariable.dicts(
            "TimeDeviation",
            (self.days,),
            lowBound=0, cat='Continuous'
        )
        
        self.variables['QualityScore'] = pulp.LpVariable.dicts(
            "QualityScore",
            (self.planting_polygons, self.days),
            lowBound=0, upBound=100, cat='Continuous'
        )
        
        # 12. NETWORK FLOW VARIABLES
        # Detailed supply chain network
        self.variables['FlowQuantity'] = pulp.LpVariable.dicts(
            "FlowQuantity",
            (self.providers, self.planting_polygons, self.species, self.days),
            lowBound=0, cat='Integer'
        )
        
        self.variables['FlowCost'] = pulp.LpVariable.dicts(
            "FlowCost",
            (self.providers, self.planting_polygons, self.species, self.days),
            lowBound=0, cat='Continuous'
        )
        
        # 13. PENALTY AND SLACK VARIABLES
        self.variables['LatePenalty'] = pulp.LpVariable.dicts(
            "LatePenalty",
            (self.planting_polygons, self.days),
            lowBound=0, cat='Continuous'
        )
        
        self.variables['CapacitySlack'] = pulp.LpVariable.dicts(
            "CapacitySlack",
            (self.days,),
            lowBound=0, cat='Continuous'
        )
        
        self.variables['DemandSlack'] = pulp.LpVariable.dicts(
            "DemandSlack",
            (self.species, self.planting_polygons),
            lowBound=0, cat='Continuous'
        )
        
        # Final day variable (for time minimization)
        if self.objective_type == 'time':
            self.variables['T_final'] = pulp.LpVariable(
                "FinalDay", lowBound=1, upBound=self.time_horizon, cat='Integer'
            )
        
        logger.info(f"Created {sum(len(v) if hasattr(v, '__len__') else 1 for v in self.variables.values())} decision variables")
    
    def _create_objective(self):
        """Create the multi-objective function with advanced cost components."""
        logger.info(f"Creating {self.objective_type} objective...")
        
        if self.objective_type == 'cost':
            # === PRIMARY COST COMPONENTS ===
            # Basic purchase and planting costs
            purchase_cost = pulp.lpSum([
                self.variables['X'][e][v][t] * (
                    PROVIDER_COSTS[v].get(e, 0) + TRANSPORT_COST_PER_PLANT
                )
                for e in self.species
                for v in self.providers
                for t in self.days
                if e in PROVIDER_COSTS[v]
            ])
            
            planting_cost = pulp.lpSum([
                self.variables['Planted'][e][p][t] * PLANTATION_COST_PER_PLANT
                for e in self.species
                for p in self.planting_polygons
                for t in self.days
            ])
            
            # === ADVANCED COST COMPONENTS ===
            
            # 1. VEHICLE USAGE COSTS (different vehicle types have different costs)
            vehicle_costs = {'standard': 100, 'large': 150, 'express': 200}
            vehicle_cost = pulp.lpSum([
                self.variables['VehicleUsed'][vt][p][t] * vehicle_costs[vt]
                for vt in ['standard', 'large', 'express']
                for p in self.planting_polygons
                for t in self.days
            ])
            
            # 2. WORKFORCE COSTS (different worker types, overtime costs)
            worker_rates = {'supervisor': 50, 'planter': 30, 'driver': 35, 'specialist': 45}
            workforce_cost = pulp.lpSum([
                self.variables['WorkerHours'][wt][p][t] * worker_rates[wt]
                for wt in worker_rates.keys()
                for p in self.planting_polygons
                for t in self.days
            ])
            
            # 3. QUALITY PREMIUM COSTS
            quality_premiums = {'premium': 50, 'standard': 20, 'basic': 0}
            quality_cost = pulp.lpSum([
                self.variables['QualityLevel'][ql][e][p][t] * quality_premiums[ql] * 
                self.variables['Planted'][e][p][t]
                for ql in quality_premiums.keys()
                for e in self.species
                for p in self.planting_polygons
                for t in self.days
            ])
            
            # 4. STORAGE ZONE ACTIVATION COSTS
            storage_cost = pulp.lpSum([
                self.variables['ZoneActive'][z][t] * 50  # Fixed cost per zone per day
                for z in range(10)
                for t in self.days
            ])
            
            # 5. RUSH ORDER PENALTIES
            rush_penalty = pulp.lpSum([
                self.variables['OrderSequence'][v][seq][t] * (seq + 1) * 100  # Higher sequence = higher cost
                for v in self.providers
                for seq in range(5)
                for t in self.days
            ])
            
            # 6. ROUTE COSTS
            route_cost = pulp.lpSum([
                self.variables['Route'][p1][p2][t] * TIME_DF.loc[p1, p2] * 25  # Cost per hour of routing
                for p1 in self.planting_polygons
                for p2 in self.planting_polygons
                for t in self.days
                if p1 != p2
            ])
            
            # 7. BATCH SETUP COSTS
            batch_setup_costs = {100: 20, 200: 30, 300: 40, 524: 50}
            batch_cost = pulp.lpSum([
                self.variables['BatchUsed'][bs][e][p][t] * batch_setup_costs[bs]
                for bs in batch_setup_costs.keys()
                for e in self.species
                for p in self.planting_polygons
                for t in self.days
            ])
            
            # 8. SUSTAINABILITY COSTS/BENEFITS
            sustainability_factors = {'eco_premium': -30, 'eco_standard': -10, 'conventional': 20}  # Negative = benefit
            sustainability_cost = pulp.lpSum([
                self.variables['SustainabilityChoice'][sl][e][t] * sustainability_factors[sl] *
                pulp.lpSum([self.variables['X'][e][v][t] for v in self.providers if e in PROVIDER_COSTS[v]])
                for sl in sustainability_factors.keys()
                for e in self.species
                for t in self.days
            ])
            
            # 9. WEATHER ADAPTATION COSTS
            weather_costs = {'sunny': 0, 'cloudy': 10, 'rainy': 100, 'windy': 50}
            weather_cost = pulp.lpSum([
                self.variables['WeatherAdjustment'][wc][t] * weather_costs[wc] *
                pulp.lpSum([self.variables['Planted'][e][p][t] 
                           for e in self.species for p in self.planting_polygons])
                for wc in weather_costs.keys()
                for t in self.days
            ])
            
            # 10. RISK MITIGATION COSTS
            risk_costs = {'weather_risk': 200, 'supply_risk': 150, 'quality_risk': 100, 'timing_risk': 120}
            risk_cost = pulp.lpSum([
                self.variables['RiskMitigation'][rf][t] * risk_costs[rf]
                for rf in risk_costs.keys()
                for t in self.days
            ])
            
            # 11. CONTINGENCY BUFFER COSTS
            buffer_cost = pulp.lpSum([
                self.variables['ContingencyBuffer'][e][t] * 5  # Cost per buffer plant
                for e in self.species
                for t in self.days
            ])
            
            # 12. DEVIATION PENALTIES
            deviation_penalty = pulp.lpSum([
                self.variables['CostDeviation'][t] * 1000 +  # Heavy penalty for cost deviations
                self.variables['TimeDeviation'][t] * 500
                for t in self.days
            ])
            
            # 13. FLOW NETWORK COSTS
            flow_cost = pulp.lpSum([
                self.variables['FlowCost'][v][p][e][t]
                for v in self.providers
                for p in self.planting_polygons
                for e in self.species
                for t in self.days
            ])
            
            # 14. LATE DELIVERY PENALTIES
            late_penalty = pulp.lpSum([
                self.variables['LatePenalty'][p][t] * 1000  # High penalty for delays
                for p in self.planting_polygons
                for t in self.days
            ])
            
            # 15. CAPACITY SLACK PENALTIES
            slack_penalty = pulp.lpSum([
                self.variables['CapacitySlack'][t] * 50 +  # Penalty for unused capacity
                pulp.lpSum([self.variables['DemandSlack'][e][p] * 2000  # High penalty for unmet demand
                           for e in self.species for p in self.planting_polygons])
                for t in self.days
            ])
            
            # 16. TIME SLOT INEFFICIENCY COSTS
            time_inefficiency = pulp.lpSum([
                self.variables['TimeSlotUsed'][p][t][ts] * (abs(ts - 12) * 5)  # Penalty for off-peak hours
                for p in self.planting_polygons
                for t in self.days
                for ts in range(24)
            ])
            
            # 17. QUALITY SCORE REWARDS (negative cost = benefit)
            quality_reward = -pulp.lpSum([
                self.variables['QualityScore'][p][t] * 10  # Reward high quality
                for p in self.planting_polygons
                for t in self.days
            ])
            
            # === COMBINE ALL COST COMPONENTS ===
            total_objective = (
                purchase_cost + planting_cost + vehicle_cost + workforce_cost +
                quality_cost + storage_cost + rush_penalty + route_cost +
                batch_cost + sustainability_cost + weather_cost + risk_cost +
                buffer_cost + deviation_penalty + flow_cost + late_penalty +
                slack_penalty + time_inefficiency + quality_reward
            )
            
            self.model += total_objective, "Total_Cost"
            
        elif self.objective_type == 'time':
            # Time objective with multiple time-related penalties
            base_time = self.variables['T_final']
            
            # Add penalties for inefficient time usage
            time_penalties = pulp.lpSum([
                self.variables['TimeDeviation'][t] * 100 +
                self.variables['LatePenalty'][p][t] * 50
                for t in self.days
                for p in self.planting_polygons
            ])
            
            # Add rewards for efficient routing
            efficiency_bonus = -pulp.lpSum([
                self.variables['Route'][p1][p2][t] * 10  # Bonus for good routing
                for p1 in self.planting_polygons
                for p2 in self.planting_polygons
                for t in self.days
                if p1 != p2 and TIME_DF.loc[p1, p2] < 1.0  # Reward short routes
            ])
            
            self.model += base_time + time_penalties + efficiency_bonus, "Project_Duration"
    
    def _add_order_constraints(self):
        """Add constraints related to nursery orders."""
        logger.info("Adding order constraints...")
        
        # Constraint 1: Max quantity per order
        for v in self.providers:
            for t in self.days:
                self.model += (
                    pulp.lpSum([self.variables['X'][e][v][t] for e in self.species 
                               if e in PROVIDER_COSTS[v]]) 
                    <= MAX_PLANTS_ORDER_PER_PROVIDER_PER_DAY * self.variables['Y'][v][t],
                    f"MaxQuantityPerOrder_{v}_{t}"
                )
    
    def _add_inventory_constraints(self):
        """Add inventory flow and acclimatization constraints."""
        logger.info("Adding inventory constraints...")
        
        # Constraint 2: Plant arrivals and start of acclimatization
        for e in self.species:
            for t in self.days:
                if t > ORDER_DELIVERY_TIME:  # Changed >= to > to avoid accessing day 0
                    arrivals = pulp.lpSum([
                        self.variables['X'][e][v][t - ORDER_DELIVERY_TIME]
                        for v in self.providers
                        if e in PROVIDER_COSTS[v]
                    ])
                    self.model += (
                        self.variables['InvAclim'][e][0][t] == arrivals,
                        f"PlantArrivals_{e}_{t}"
                    )
                else:
                    self.model += (
                        self.variables['InvAclim'][e][0][t] == 0,
                        f"PlantArrivals_{e}_{t}"
                    )
        
        # Constraint 3: Acclimatization flow
        for e in self.species:
            for d in range(1, MIN_ACCLIMATION_DAYS):
                for t in self.days:
                    if t > 1:  # Changed >= to > to avoid accessing day 0
                        self.model += (
                            self.variables['InvAclim'][e][d][t] == 
                            self.variables['InvAclim'][e][d-1][t-1],
                            f"AcclimatizationFlow_{e}_{d}_{t}"
                        )
                    else:
                        self.model += (
                            self.variables['InvAclim'][e][d][t] == 0,
                            f"AcclimatizationFlow_{e}_{d}_{t}"
                        )
        
        # Constraint 4: Available inventory balance
        for e in self.species:
            for t in self.days:
                if t == 1:
                    # First day - no previous inventory
                    shipments_out = pulp.lpSum([
                        self.variables['S'][e][p][t] 
                        for p in self.planting_polygons
                    ])
                    self.model += (
                        self.variables['InvDisp'][e][t] == 0 - shipments_out,
                        f"InventoryBalance_{e}_{t}"
                    )
                else:
                    prev_available = self.variables['InvDisp'][e][t-1]
                    completed_acclimation = self.variables['InvAclim'][e][MIN_ACCLIMATION_DAYS-1][t-1]
                    shipments_out = pulp.lpSum([
                        self.variables['S'][e][p][t] 
                        for p in self.planting_polygons
                    ])
                    
                    self.model += (
                        self.variables['InvDisp'][e][t] == 
                        prev_available + completed_acclimation - shipments_out,
                        f"InventoryBalance_{e}_{t}"
                    )
    
    def _add_capacity_constraints(self):
        """Add warehouse and transport capacity constraints."""
        logger.info("Adding capacity constraints...")
        
        # Constraint 5: Warehouse capacity
        for t in self.days:
            total_inventory = (
                pulp.lpSum([self.variables['InvDisp'][e][t] for e in self.species]) +
                pulp.lpSum([
                    self.variables['InvAclim'][e][d][t]
                    for e in self.species
                    for d in self.acclimation_stages
                ])
            )
            self.model += (
                total_inventory <= WAREHOUSE_CAPACITY,
                f"WarehouseCapacity_{t}"
            )
    
    def _add_demand_constraints(self):
        """Add demand fulfillment constraints."""
        logger.info("Adding demand constraints...")
        
        # Constraint 6: Demand fulfillment (with slack for flexibility)
        for p in self.planting_polygons:
            for e in self.species:
                total_planted = pulp.lpSum([
                    self.variables['Planted'][e][p][t] for t in self.days
                ])
                demand_value = self.demand.loc[p, e]
                self.model += (
                    total_planted + self.variables['DemandSlack'][e][p] >= demand_value,
                    f"DemandFulfillment_{p}_{e}"
                )
        
        # Constraint 7: Planting logic (shipment = planted)
        for e in self.species:
            for p in self.planting_polygons:
                for t in self.days:
                    self.model += (
                        self.variables['Planted'][e][p][t] == self.variables['S'][e][p][t],
                        f"PlantingLogic_{e}_{p}_{t}"
                    )
    
    def _add_operational_constraints(self):
        """Add operational constraints for transport and work schedule."""
        logger.info("Adding operational constraints...")
        
        # Constraint 8: Internal transport capacity
        for p in self.planting_polygons:
            for t in self.days:
                total_shipment = pulp.lpSum([
                    self.variables['S'][e][p][t] for e in self.species
                ])
                self.model += (
                    total_shipment <= self.variables['N_trips'][p][t] * VAN_CAPACITY,
                    f"TransportCapacity_{p}_{t}"
                )
        
        # Constraint 9: Workday restrictions
        for e in self.species:
            for p in self.planting_polygons:
                for t in self.days:
                    if not self.workdays[t]:  # Non-workday
                        self.model += (
                            self.variables['S'][e][p][t] == 0,
                            f"NoWeekendShipment_{e}_{p}_{t}"
                        )
        
        # Separate constraint for trips to avoid duplication
        for p in self.planting_polygons:
            for t in self.days:
                if not self.workdays[t]:  # Non-workday
                    self.model += (
                        self.variables['N_trips'][p][t] == 0,
                        f"NoWeekendTrips_{p}_{t}"
                    )
    
    def _add_time_constraints(self):
        """Add daily work hour constraints."""
        logger.info("Adding time constraints...")
        
        # Constraint 10: Daily work hour limit
        for t in self.days:
            if self.workdays[t]:  # Only for workdays
                # Treatment time: Fixed time per species if any plants are shipped
                # Use binary variables to model "if species e is used on day t"
                species_used = {}
                for e in self.species:
                    species_used[e] = pulp.LpVariable(f"SpeciesUsed_{e}_{t}", cat='Binary')
                    # If any plants of species e are shipped, species_used[e] = 1
                    total_species_shipment = pulp.lpSum([
                        self.variables['S'][e][p][t] for p in self.planting_polygons
                    ])
                    # Big M constraint: Bidirectional linking
                    M = 10000  # Big M (larger than any possible shipment)
                    
                    # If total_species_shipment > 0, then species_used[e] = 1
                    self.model += (
                        total_species_shipment <= M * species_used[e],
                        f"SpeciesUsage_Upper_{e}_{t}"
                    )
                    
                    # If species_used[e] = 0, then total_species_shipment = 0
                    # Equivalently: total_species_shipment >= 1 * species_used[e] (if any shipment, binary must be 1)
                    self.model += (
                        total_species_shipment >= species_used[e],
                        f"SpeciesUsage_Lower_{e}_{t}"
                    )
                
                treatment_time = pulp.lpSum([
                    species_used[e] * self.treatment_times[e]
                    for e in self.species
                ])
                
                # Loading/unloading time
                handling_time = pulp.lpSum([
                    self.variables['S'][e][p][t] * 2 * (LOAD_TIME_PER_PLANT + UNLOAD_TIME_PER_PLANT)
                    for e in self.species
                    for p in self.planting_polygons
                ])
                
                # Travel time (round trip)
                travel_time = pulp.lpSum([
                    self.variables['N_trips'][p][t] * 2 * TIME_DF.loc[self.warehouse_id, p]
                    for p in self.planting_polygons
                ])
                
                total_time = treatment_time + handling_time + travel_time
                
                self.model += (
                    total_time <= LABOR_TIME,
                    f"DailyWorkHours_{t}"
                )
    
    def _add_time_objective_constraints(self):
        """Add constraints for time minimization objective."""
        if self.objective_type == 'time':
            logger.info("Adding time objective constraints...")
            
            # Link final day to actual activities
            M = self.time_horizon
            for t in self.days:
                # If any activity happens on day t, T_final >= t
                total_activity = (
                    pulp.lpSum([self.variables['S'][e][p][t] 
                               for e in self.species 
                               for p in self.planting_polygons]) +
                    pulp.lpSum([self.variables['X'][e][v][t]
                               for e in self.species
                               for v in self.providers
                               if e in PROVIDER_COSTS[v]])
                )
                
                self.model += (
                    self.variables['T_final'] >= t - M * (1 - pulp.lpSum([
                        self.variables['Y'][v][t] for v in self.providers
                    ]) / len(self.providers)),
                    f"FinalDayLowerBound_{t}"
                )
    
    def _add_advanced_constraints(self):
        """Add advanced constraints for comprehensive optimization."""
        logger.info("Adding advanced constraints...")
        
        # === 1. MULTI-VEHICLE FLEET CONSTRAINTS ===
        logger.info("Adding multi-vehicle fleet constraints...")
        
        vehicle_capacities = {'standard': VAN_CAPACITY, 'large': int(VAN_CAPACITY * 1.5), 'express': int(VAN_CAPACITY * 0.8)}
        
        # Vehicle capacity linking constraints
        for vt in ['standard', 'large', 'express']:
            for p in self.planting_polygons:
                for t in self.days:
                    # Link vehicle usage to capacity
                    total_shipment = pulp.lpSum([self.variables['S'][e][p][t] for e in self.species])
                    self.model += (
                        self.variables['VehicleCapacity'][vt][p][t] >= 
                        total_shipment - (1 - self.variables['VehicleUsed'][vt][p][t]) * 10000,
                        f"VehicleCapacityLink_{vt}_{p}_{t}"
                    )
                    
                    # Vehicle capacity limits
                    self.model += (
                        self.variables['VehicleCapacity'][vt][p][t] <= 
                        vehicle_capacities[vt] * self.variables['VehicleUsed'][vt][p][t],
                        f"VehicleCapacityLimit_{vt}_{p}_{t}"
                    )
        
        # Only one vehicle type per polygon per day
        for p in self.planting_polygons:
            for t in self.days:
                self.model += (
                    pulp.lpSum([self.variables['VehicleUsed'][vt][p][t] 
                               for vt in ['standard', 'large', 'express']]) <= 1,
                    f"SingleVehicleType_{p}_{t}"
                )
        
        # === 2. DETAILED TIMING CONSTRAINTS ===
        logger.info("Adding detailed timing constraints...")
        
        # Time slot usage constraints
        for p in self.planting_polygons:
            for t in self.days:
                if self.workdays[t]:  # Only on workdays
                    # At most 8 time slots can be used (8-hour workday)
                    self.model += (
                        pulp.lpSum([self.variables['TimeSlotUsed'][p][t][ts] 
                                   for ts in range(6, 18)]) <= 8,  # Work hours 6 AM to 6 PM
                        f"WorkingHoursLimit_{p}_{t}"
                    )
                    
                    # Start and end time consistency
                    for ts in range(6, 18):  # Only check working hours
                        self.model += (
                            self.variables['StartTime'][p][t] <= ts + 24 * (1 - self.variables['TimeSlotUsed'][p][t][ts]),
                            f"StartTimeConsistency_{p}_{t}_{ts}"
                        )
                        
                        self.model += (
                            self.variables['EndTime'][p][t] >= ts - 24 * (1 - self.variables['TimeSlotUsed'][p][t][ts]),
                            f"EndTimeConsistency_{p}_{t}_{ts}"
                        )
                    
                    # End time must be after start time
                    self.model += (
                        self.variables['EndTime'][p][t] >= self.variables['StartTime'][p][t],
                        f"TimeOrdering_{p}_{t}"
                    )
                else:
                    # No work on non-workdays
                    for ts in range(24):
                        self.model += (
                            self.variables['TimeSlotUsed'][p][t][ts] == 0,
                            f"NoWorkNonWorkday_{p}_{t}_{ts}"
                        )
        
        # === 3. WORKFORCE ALLOCATION CONSTRAINTS ===
        logger.info("Adding workforce allocation constraints...")
        
        worker_limits = {'supervisor': 2, 'planter': 10, 'driver': 3, 'specialist': 1}
        
        # Worker availability limits
        for wt in worker_limits.keys():
            for t in self.days:
                if self.workdays[t]:
                    total_workers = pulp.lpSum([self.variables['WorkerAssigned'][wt][p][t] 
                                               for p in self.planting_polygons])
                    self.model += (
                        total_workers <= worker_limits[wt],
                        f"WorkerLimit_{wt}_{t}"
                    )
        
        # Worker hour constraints
        for wt in worker_limits.keys():
            for p in self.planting_polygons:
                for t in self.days:
                    if self.workdays[t]:
                        # Hours must be consistent with assignment
                        self.model += (
                            self.variables['WorkerHours'][wt][p][t] <= 
                            8 * self.variables['WorkerAssigned'][wt][p][t],
                            f"WorkerHoursLimit_{wt}_{p}_{t}"
                        )
                        
                        # Minimum hours if assigned
                        self.model += (
                            self.variables['WorkerHours'][wt][p][t] >= 
                            self.variables['WorkerAssigned'][wt][p][t],
                            f"MinWorkerHours_{wt}_{p}_{t}"
                        )
        
        # === 4. QUALITY AND ENVIRONMENTAL CONSTRAINTS ===
        logger.info("Adding quality and environmental constraints...")
        
        # At most one quality level per species per polygon per day
        for e in self.species:
            for p in self.planting_polygons:
                for t in self.days:
                    quality_sum = pulp.lpSum([self.variables['QualityLevel'][ql][e][p][t] 
                                             for ql in ['premium', 'standard', 'basic']])
                    self.model += (
                        quality_sum <= 1,
                        f"QualitySelection_{e}_{p}_{t}"
                    )
                    
                    # Link quality to planted quantity using Big-M
                    planted = self.variables['Planted'][e][p][t]
                    for ql in ['premium', 'standard', 'basic']:
                        self.model += (
                            planted <= 10000 * self.variables['QualityLevel'][ql][e][p][t],
                            f"QualityLink_{ql}_{e}_{p}_{t}"
                        )
        
        # Weather adaptation constraints
        for t in self.days:
            # Exactly one weather condition per day
            self.model += (
                pulp.lpSum([self.variables['WeatherAdjustment'][wc][t] 
                           for wc in ['sunny', 'cloudy', 'rainy', 'windy']]) == 1,
                f"WeatherSelection_{t}"
            )
        
        # === 5. STORAGE ALLOCATION CONSTRAINTS ===
        logger.info("Adding storage allocation constraints...")
        
        zone_capacities = [1000] * 10  # Each zone has 1000 plant capacity
        
        # Zone capacity constraints
        for z in range(10):
            for t in self.days:
                total_in_zone = pulp.lpSum([self.variables['StorageAllocation'][e][z][t] 
                                           for e in self.species])
                self.model += (
                    total_in_zone <= zone_capacities[z] * self.variables['ZoneActive'][z][t],
                    f"ZoneCapacity_{z}_{t}"
                )
        
        # Storage balance constraints
        for e in self.species:
            for t in self.days:
                total_stored = pulp.lpSum([self.variables['StorageAllocation'][e][z][t] 
                                          for z in range(10)])
                self.model += (
                    total_stored == self.variables['InvDisp'][e][t],
                    f"StorageBalance_{e}_{t}"
                )
        
        # === 6. SEQUENTIAL ORDERING CONSTRAINTS ===
        logger.info("Adding sequential ordering constraints...")
        
        # Order sequence constraints
        for v in self.providers:
            for t in self.days:
                # At most one sequence per provider per day
                self.model += (
                    pulp.lpSum([self.variables['OrderSequence'][v][seq][t] 
                               for seq in range(5)]) <= self.variables['Y'][v][t],
                    f"OrderSequenceLimit_{v}_{t}"
                )
        
        # Order priority constraints
        for e in self.species:
            for v in self.providers:
                if e in PROVIDER_COSTS[v]:
                    for t in self.days:
                        # Priority must be reasonable if ordering
                        order_qty = self.variables['X'][e][v][t]
                        priority = self.variables['OrderPriority'][e][v][t]
                        self.model += (
                            priority >= 1,  # Minimum priority
                            f"PriorityMinimum_{e}_{v}_{t}"
                        )
                        
                        self.model += (
                            priority <= 10,  # Maximum priority
                            f"PriorityMaximum_{e}_{v}_{t}"
                        )
        
        # === 7. BATCH PROCESSING CONSTRAINTS ===
        logger.info("Adding batch processing constraints...")
        
        # Batch size selection
        for e in self.species:
            for p in self.planting_polygons:
                for t in self.days:
                    # At most one batch size per species per polygon per day
                    self.model += (
                        pulp.lpSum([self.variables['BatchUsed'][bs][e][p][t] 
                                   for bs in [100, 200, 300, 524]]) <= 1,
                        f"BatchSelection_{e}_{p}_{t}"
                    )
                    
                    # Batch count consistency
                    planted = self.variables['Planted'][e][p][t]
                    for bs in [100, 200, 300, 524]:
                        self.model += (
                            planted <= bs * self.variables['BatchCount'][bs][e][p][t],
                            f"BatchCountUpper_{bs}_{e}_{p}_{t}"
                        )
                        
                        # Link batch used to batch count
                        self.model += (
                            self.variables['BatchCount'][bs][e][p][t] <= 
                            1000 * self.variables['BatchUsed'][bs][e][p][t],
                            f"BatchUsedLink_{bs}_{e}_{p}_{t}"
                        )
        
        # === 8. SUSTAINABILITY METRICS CONSTRAINTS ===
        logger.info("Adding sustainability metrics constraints...")
        
        # Sustainability choice constraints
        for e in self.species:
            for t in self.days:
                # At most one sustainability level per species per day
                self.model += (
                    pulp.lpSum([self.variables['SustainabilityChoice'][sl][e][t] 
                               for sl in ['eco_premium', 'eco_standard', 'conventional']]) <= 1,
                    f"SustainabilitySelection_{e}_{t}"
                )
        
        # === 9. RISK MANAGEMENT CONSTRAINTS ===
        logger.info("Adding risk management constraints...")
        
        # Risk mitigation constraints
        for t in self.days:
            # At least some risk consideration on active days
            total_activity = pulp.lpSum([self.variables['Planted'][e][p][t] 
                                       for e in self.species for p in self.planting_polygons])
            total_risk_factors = pulp.lpSum([self.variables['RiskMitigation'][rf][t] 
                                           for rf in ['weather_risk', 'supply_risk', 'quality_risk', 'timing_risk']])
            
            # If there's activity, there must be risk consideration
            self.model += (
                total_risk_factors * 1000 >= total_activity,
                f"RiskConsideration_{t}"
            )
        
        # Contingency buffer constraints
        for e in self.species:
            for t in self.days:
                # Buffer proportional to demand but limited
                total_demand = sum([self.demand.loc[p, e] for p in self.planting_polygons])
                self.model += (
                    self.variables['ContingencyBuffer'][e][t] <= total_demand * 0.1,  # Max 10% buffer
                    f"ContingencyLimit_{e}_{t}"
                )
        
        # === 10. PENALTY AND DEVIATION CONSTRAINTS ===
        logger.info("Adding penalty and deviation constraints...")
        
        # Cost deviation tracking
        for t in self.days:
            daily_cost = pulp.lpSum([
                self.variables['X'][e][v][t] * PROVIDER_COSTS[v].get(e, 0)
                for e in self.species
                for v in self.providers
                if e in PROVIDER_COSTS[v]
            ])
            
            target_daily_cost = 50000  # Target daily cost
            self.model += (
                self.variables['CostDeviation'][t] >= daily_cost - target_daily_cost,
                f"CostDeviationUpper_{t}"
            )
            
            self.model += (
                self.variables['CostDeviation'][t] >= target_daily_cost - daily_cost,
                f"CostDeviationLower_{t}"
            )
        
        # Quality score constraints
        for p in self.planting_polygons:
            for t in self.days:
                # Quality score based on quality choices (simplified)
                quality_contribution = pulp.lpSum([
                    self.variables['QualityLevel']['premium'][e][p][t] * 100 +
                    self.variables['QualityLevel']['standard'][e][p][t] * 70 +
                    self.variables['QualityLevel']['basic'][e][p][t] * 40
                    for e in self.species
                ])
                
                self.model += (
                    self.variables['QualityScore'][p][t] <= quality_contribution,
                    f"QualityScoreUpper_{p}_{t}"
                )
        
        # === 11. ADVANCED FLOW CONSTRAINTS ===
        logger.info("Adding advanced flow constraints...")
        
        # Flow quantity and cost linking
        for v in self.providers:
            for p in self.planting_polygons:
                for e in self.species:
                    if e in PROVIDER_COSTS[v]:
                        for t in self.days:
                            # Flow cost calculation (simplified)
                            base_cost = PROVIDER_COSTS[v][e] + TRANSPORT_COST_PER_PLANT
                            
                            self.model += (
                                self.variables['FlowCost'][v][p][e][t] >= 
                                self.variables['FlowQuantity'][v][p][e][t] * base_cost,
                                f"FlowCostCalculation_{v}_{p}_{e}_{t}"
                            )
                            
                            # Flow quantity limits
                            self.model += (
                                self.variables['FlowQuantity'][v][p][e][t] <= 
                                self.variables['X'][e][v][t],
                                f"FlowQuantityLimit_{v}_{p}_{e}_{t}"
                            )
        
        # === 12. LATE PENALTY CALCULATION ===
        logger.info("Adding late penalty calculations...")
        
        # Late penalty calculation
        for p in self.planting_polygons:
            for t in self.days:
                # Simple late penalty based on expected progress
                expected_completion = 0.5  # Expected fraction completed by day t
                total_demand_polygon = sum([self.demand.loc[p, e] for e in self.species])
                actual_planted = pulp.lpSum([
                    pulp.lpSum([self.variables['Planted'][e][p][day] for day in self.days if day <= t])
                    for e in self.species
                ])
                
                expected_planted = expected_completion * total_demand_polygon * t / self.time_horizon
                
                self.model += (
                    self.variables['LatePenalty'][p][t] >= expected_planted - actual_planted,
                    f"LatePenaltyCalc_{p}_{t}"
                )
        
        # Capacity slack calculation
        for t in self.days:
            used_capacity = pulp.lpSum([
                self.variables['InvDisp'][e][t] + 
                pulp.lpSum([self.variables['InvAclim'][e][d][t] for d in self.acclimation_stages])
                for e in self.species
            ])
            
            self.model += (
                self.variables['CapacitySlack'][t] >= WAREHOUSE_CAPACITY - used_capacity,
                f"CapacitySlackCalc_{t}"
            )
        
        logger.info("Advanced constraints added successfully.")
    
    def diagnose_infeasibility(self):
        """Diagnose potential infeasibility issues in the model."""
        logger.info("Diagnosing potential infeasibility issues...")
        
        # Check total demand vs time horizon
        total_demand = self.demand.sum().sum()
        logger.info(f"Total demand across all polygons and species: {total_demand}")
        
        # Check if we have enough time to fulfill demand
        max_daily_capacity = len(self.planting_polygons) * VAN_CAPACITY
        workdays_in_horizon = sum(1 for d in self.days if self.workdays[d])
        total_capacity = max_daily_capacity * workdays_in_horizon
        
        logger.info(f"Maximum daily planting capacity: {max_daily_capacity}")
        logger.info(f"Workdays in horizon: {workdays_in_horizon}")
        logger.info(f"Total theoretical capacity: {total_capacity}")
        
        if total_demand > total_capacity:
            logger.warning("INFEASIBILITY: Total demand exceeds theoretical capacity!")
        
        # Check provider capacity
        total_provider_capacity = 0
        for provider in self.providers:
            provider_species = [e for e in self.species if e in PROVIDER_COSTS[provider]]
            daily_capacity = MAX_PLANTS_ORDER_PER_PROVIDER_PER_DAY
            provider_total = daily_capacity * len(self.days)
            total_provider_capacity += provider_total
            logger.info(f"Provider {provider} can supply species {provider_species}, "
                       f"max daily: {daily_capacity}, total capacity: {provider_total}")
        
        logger.info(f"Total provider capacity: {total_provider_capacity}")
        if total_demand > total_provider_capacity:
            logger.warning("INFEASIBILITY: Total demand exceeds provider capacity!")
        
        # Check acclimatization timing
        min_days_needed = MIN_ACCLIMATION_DAYS + ORDER_DELIVERY_TIME + 1
        logger.info(f"Minimum days needed for order->plant cycle: {min_days_needed}")
        if self.time_horizon < min_days_needed:
            logger.warning("INFEASIBILITY: Time horizon too short for acclimatization!")
    
    def diagnose_time_constraints(self):
        """Diagnose time constraint feasibility in detail."""
        logger.info("Diagnosing time constraint feasibility...")
        
        # Calculate minimum time needed per polygon per day
        for p in self.planting_polygons:
            demand_for_polygon = self.demand.loc[p].sum()
            logger.info(f"Polygon {p} total demand: {demand_for_polygon}")
            
            # Calculate travel time to this polygon
            travel_time_per_trip = 2 * TIME_DF.loc[self.warehouse_id, p]  # Round trip
            logger.info(f"  Travel time per round trip: {travel_time_per_trip:.2f} hours")
            
            # Calculate minimum trips needed
            min_trips = int(np.ceil(demand_for_polygon / VAN_CAPACITY))
            logger.info(f"  Minimum trips needed: {min_trips}")
            
            # Calculate time for minimum viable daily operation
            min_plants_per_day = min(VAN_CAPACITY, demand_for_polygon)
            
            # Treatment time (FIXED per species, not per plant - worst case all 10 species)
            treatment_time = len(self.species) * NORMAL_TREATMENT_HR_PER_PLANT
            
            # Loading/unloading time
            handling_time = min_plants_per_day * 2 * (LOAD_TIME_PER_PLANT + UNLOAD_TIME_PER_PLANT)
            
            # Travel time for one trip
            travel_time = travel_time_per_trip
            
            min_daily_time = treatment_time + handling_time + travel_time
            
            logger.info(f"  Minimum daily time for {min_plants_per_day} plants:")
            logger.info(f"    Treatment: {treatment_time:.3f} hours")
            logger.info(f"    Handling: {handling_time:.3f} hours") 
            logger.info(f"    Travel: {travel_time:.3f} hours")
            logger.info(f"    Total: {min_daily_time:.3f} hours")
            logger.info(f"    Available: {LABOR_TIME} hours")
            
            if min_daily_time > LABOR_TIME:
                logger.error(f"  INFEASIBLE: Minimum daily time ({min_daily_time:.3f}) > Available time ({LABOR_TIME})")
            else:
                logger.info(f"  FEASIBLE: Minimum daily time fits in available hours")
    
    def suggest_parameter_adjustments(self):
        """Suggest parameter adjustments to make the model feasible without changing constraints."""
        logger.info("Suggesting parameter adjustments for feasibility...")
        
        # Check if time horizon is sufficient
        min_delivery_and_acclimatization = ORDER_DELIVERY_TIME + MIN_ACCLIMATION_DAYS + 1
        total_demand = self.demand.sum().sum()
        workdays_in_horizon = sum(1 for d in self.days if self.workdays[d])
        
        # Calculate realistic daily capacity considering time constraints
        max_plants_per_polygon_per_day = VAN_CAPACITY  # Conservative estimate
        realistic_daily_capacity = len(self.planting_polygons) * max_plants_per_polygon_per_day
        
        # But we need to check if time allows this
        total_time_for_max_capacity = 0
        for p in self.planting_polygons:
            travel_time = 2 * TIME_DF.loc[self.warehouse_id, p]
            handling_time = max_plants_per_polygon_per_day * 2 * (LOAD_TIME_PER_PLANT + UNLOAD_TIME_PER_PLANT)
            total_time_for_max_capacity += travel_time + handling_time
        
        # Add treatment time once per species (not per polygon)
        treatment_time = len(self.species) * NORMAL_TREATMENT_HR_PER_PLANT
        total_time_for_max_capacity += treatment_time
        
        if total_time_for_max_capacity > LABOR_TIME:
            # Time constraint is binding, need to reduce realistic capacity
            time_scaling_factor = LABOR_TIME / total_time_for_max_capacity
            realistic_daily_capacity *= time_scaling_factor
            logger.warning(f"Time constraints reduce realistic daily capacity to {realistic_daily_capacity:.0f}")
        
        min_days_needed = int(np.ceil(total_demand / realistic_daily_capacity)) + min_delivery_and_acclimatization
        
        logger.info(f"Current time horizon: {self.time_horizon} days")
        logger.info(f"Minimum needed horizon: {min_days_needed} days")
        
        if self.time_horizon < min_days_needed:
            logger.error(f"TIME HORIZON TOO SHORT: Need at least {min_days_needed} days")
            suggested_horizon = min_days_needed + 10  # Add buffer
            logger.info(f"SUGGESTION: Increase time_horizon to {suggested_horizon} days")
        
        # Check if we can redistribute work across available days
        logger.info(f"Workdays available: {workdays_in_horizon}")
        logger.info(f"Demand per workday needed: {total_demand / workdays_in_horizon:.1f}")
        logger.info(f"Realistic capacity per workday: {realistic_daily_capacity:.1f}")
        
        if total_demand / workdays_in_horizon > realistic_daily_capacity:
            logger.error("INSUFFICIENT CAPACITY: Even with perfect distribution, cannot meet demand")
            additional_days_needed = int(np.ceil(total_demand / realistic_daily_capacity)) - workdays_in_horizon
            logger.info(f"SUGGESTION: Need {additional_days_needed} more workdays")
    
    def build_relaxed_model(self):
        """Build a relaxed version of the model for feasibility testing."""
        logger.info("Building relaxed optimization model...")
        
        # Initialize model
        sense = pulp.LpMinimize
        self.model = pulp.LpProblem("Reforestation_Optimization_Relaxed", sense)
        
        # Create components
        self._create_variables()
        self._create_objective()
        
        # Add constraints (with some relaxations)
        self._add_order_constraints()
        self._add_inventory_constraints_relaxed()  # Relaxed version
        self._add_capacity_constraints()
        self._add_demand_constraints()
        self._add_operational_constraints_relaxed()  # Relaxed version
        # Skip time constraints for now to test feasibility
        
        logger.info(f"Relaxed model built with {len(self.model.variables())} variables "
                   f"and {len(self.model.constraints)} constraints")
    
    def _add_inventory_constraints_relaxed(self):
        """Add relaxed inventory flow and acclimatization constraints."""
        logger.info("Adding relaxed inventory constraints...")
        
        # Constraint 2: Plant arrivals and start of acclimatization (relaxed)
        for e in self.species:
            for t in self.days:
                if t > ORDER_DELIVERY_TIME:
                    arrivals = pulp.lpSum([
                        self.variables['X'][e][v][t - ORDER_DELIVERY_TIME]
                        for v in self.providers
                        if e in PROVIDER_COSTS[v]
                    ])
                    # Allow some slack in arrivals
                    self.model += (
                        self.variables['InvAclim'][e][0][t] >= arrivals,
                        f"PlantArrivals_{e}_{t}"
                    )
                else:
                    self.model += (
                        self.variables['InvAclim'][e][0][t] >= 0,
                        f"PlantArrivals_{e}_{t}"
                    )
        
        # Constraint 3: Acclimatization flow (simplified)
        for e in self.species:
            for d in range(1, MIN_ACCLIMATION_DAYS):
                for t in self.days:
                    if t > d:  # Ensure we don't access negative indices
                        self.model += (
                            self.variables['InvAclim'][e][d][t] >= 
                            self.variables['InvAclim'][e][d-1][t-1] - 1000,  # Allow some slack
                            f"AcclimatizationFlow_{e}_{d}_{t}"
                        )
        
        # Constraint 4: Available inventory balance (simplified)
        for e in self.species:
            for t in self.days:
                if t == 1:
                    self.model += (
                        self.variables['InvDisp'][e][t] >= 0,
                        f"InventoryBalance_{e}_{t}"
                    )
                elif t > MIN_ACCLIMATION_DAYS + ORDER_DELIVERY_TIME:
                    # Only enforce after sufficient time has passed
                    prev_available = self.variables['InvDisp'][e][t-1]
                    completed_acclimation = self.variables['InvAclim'][e][MIN_ACCLIMATION_DAYS-1][t-1]
                    shipments_out = pulp.lpSum([
                        self.variables['S'][e][p][t] 
                        for p in self.planting_polygons
                    ])
                    
                    self.model += (
                        self.variables['InvDisp'][e][t] >= 
                        prev_available + completed_acclimation - shipments_out,
                        f"InventoryBalance_{e}_{t}"
                    )
    
    def _add_operational_constraints_relaxed(self):
        """Add relaxed operational constraints."""
        logger.info("Adding relaxed operational constraints...")
        
        # Constraint 8: Internal transport capacity (relaxed)
        for p in self.planting_polygons:
            for t in self.days:
                total_shipment = pulp.lpSum([
                    self.variables['S'][e][p][t] for e in self.species
                ])
                # Allow multiple trips but with reasonable bounds
                self.model += (
                    total_shipment <= self.variables['N_trips'][p][t] * VAN_CAPACITY * 2,  # Allow 2x capacity
                    f"TransportCapacity_{p}_{t}"
                )
                
                # Reasonable upper bound on trips
                self.model += (
                    self.variables['N_trips'][p][t] <= 10,  # Max 10 trips per day per polygon
                    f"MaxTrips_{p}_{t}"
                )
        
        # Constraint 9: Workday restrictions (keep strict)
        for e in self.species:
            for p in self.planting_polygons:
                for t in self.days:
                    if not self.workdays[t]:  # Non-workday
                        self.model += (
                            self.variables['S'][e][p][t] == 0,
                            f"NoWeekendShipment_{e}_{p}_{t}"
                        )
        
        for p in self.planting_polygons:
            for t in self.days:
                if not self.workdays[t]:  # Non-workday
                    self.model += (
                        self.variables['N_trips'][p][t] == 0,
                        f"NoWeekendTrips_{p}_{t}"
                    )
    
    def build_model(self):
        """Build the complete optimization model."""
        logger.info("Building optimization model...")
        
        # Initialize model
        sense = pulp.LpMinimize
        self.model = pulp.LpProblem("Reforestation_Optimization", sense)
        
        # Create components
        self._create_variables()
        self._create_objective()
        
        # Add constraints
        self._add_order_constraints()
        self._add_inventory_constraints()
        self._add_capacity_constraints()
        self._add_demand_constraints()
        self._add_operational_constraints()
        self._add_time_constraints()
        
        if self.objective_type == 'time':
            self._add_time_objective_constraints()
        
        # Add advanced constraints
        self._add_advanced_constraints()
        
        logger.info(f"Model built with {len(self.model.variables())} variables "
                   f"and {len(self.model.constraints)} constraints")
    
    def solve(self, solver_name: str = 'PULP_CBC_CMD', time_limit: Optional[int] = None):
        """
        Solve the optimization model.
        
        Args:
            solver_name: PuLP solver name
            time_limit: Time limit in seconds (None for no limit)
        """
        if self.model is None:
            raise ValueError("Model not built. Call build_model() first.")
        
        logger.info(f"Solving model with {solver_name}...")
        
        # Configure solver
        if solver_name == 'PULP_CBC_CMD':
            solver = pulp.PULP_CBC_CMD(timeLimit=time_limit, msg=1)
        else:
            solver = pulp.getSolver(solver_name)
        
        # Solve with precise timing
        start_time = datetime.now()
        self.model.solve(solver)
        end_time = datetime.now()
        
        # Store solve time in seconds
        solve_duration = end_time - start_time
        self.solve_time = solve_duration.total_seconds()
        
        self.solution_status = pulp.LpStatus[self.model.status]
        
        logger.info(f"Solve completed in {solve_duration}")
        logger.info(f"Solve time: {self.solve_time:.3f} seconds")
        logger.info(f"Status: {self.solution_status}")
        
        if self.model.status == pulp.LpStatusOptimal:
            logger.info(f"Optimal value: {pulp.value(self.model.objective):,.2f}")
        
        return self.model.status
    
    def get_solution_summary(self) -> Dict:
        """Get a summary of the solution."""
        if self.model is None or self.model.status != pulp.LpStatusOptimal:
            return {"status": "No optimal solution available"}
        
        summary = {
            "status": self.solution_status,
            "objective_value": pulp.value(self.model.objective),
            "solve_time": "N/A",  # Would need to track this
        }
        
        # Add specific metrics based on objective type
        if self.objective_type == 'cost':
            summary["total_cost"] = pulp.value(self.model.objective)
        elif self.objective_type == 'time':
            summary["project_duration"] = int(pulp.value(self.variables['T_final']))
        
        return summary
    
    def extract_solution(self) -> Dict:
        """Extract detailed solution results."""
        if self.model is None or self.model.status != pulp.LpStatusOptimal:
            return {}
        
        logger.info("Extracting solution...")
        
        solution = {
            "orders": [],
            "shipments": [],
            "inventory": [],
            "summary": self.get_solution_summary()
        }
        
        # Extract orders
        for v in self.providers:
            for t in self.days:
                if self.variables['Y'][v][t].varValue and self.variables['Y'][v][t].varValue > 0.5:
                    order_details = []
                    for e in self.species:
                        if e in PROVIDER_COSTS[v]:
                            qty = self.variables['X'][e][v][t].varValue
                            if qty and qty > 0:
                                order_details.append({
                                    'species': e,
                                    'quantity': int(qty)
                                })
                    
                    if order_details:
                        solution["orders"].append({
                            'day': t,
                            'provider': v,
                            'species_quantities': order_details
                        })
        
        # Extract shipments/plantings
        for p in self.planting_polygons:
            for t in self.days:
                shipment_details = []
                for e in self.species:
                    qty = self.variables['S'][e][p][t].varValue
                    if qty and qty > 0:
                        shipment_details.append({
                            'species': e,
                            'quantity': int(qty)
                        })
                
                if shipment_details:
                    trips = self.variables['N_trips'][p][t].varValue
                    solution["shipments"].append({
                        'day': t,
                        'polygon': p,
                        'species_quantities': shipment_details,
                        'trips': int(trips) if trips else 0
                    })
        
        return solution
    
    def print_solution(self):
        """Print a formatted solution report."""
        solution = self.extract_solution()
        
        if not solution:
            print("No solution available")
            return
        
        print("\n" + "="*60)
        print("REFORESTATION OPTIMIZATION SOLUTION")
        print("="*60)
        
        print(f"\nStatus: {solution['summary']['status']}")
        print(f"Objective Value: {solution['summary']['objective_value']:.2f}")
        
        if solution.get('orders'):
            print(f"\n--- ORDERS ({len(solution['orders'])} total) ---")
            for order in sorted(solution['orders'], key=lambda x: x['day']):
                print(f"Day {order['day']}: {order['provider']}")
                for spec in order['species_quantities']:
                    print(f"  Species {spec['species']}: {spec['quantity']} plants")
        
        if solution.get('shipments'):
            print(f"\n--- SHIPMENTS ({len(solution['shipments'])} total) ---")
            for shipment in sorted(solution['shipments'], key=lambda x: (x['day'], x['polygon'])):
                print(f"Day {shipment['day']}: Polygon {shipment['polygon']} ({shipment['trips']} trips)")
                for spec in shipment['species_quantities']:
                    print(f"  Species {spec['species']}: {spec['quantity']} plants")
    
    def extract_daily_data(self) -> Dict:
        """Extract detailed daily data for comparison with heuristic approach."""
        if self.model is None or self.model.status != pulp.LpStatusOptimal:
            return {}
        
        logger.info("Extracting detailed daily data...")
        
        daily_data = {}
        
        for day in self.days:
            daily_data[day] = {
                'orders_created': [],
                'orders_arrived': [],
                'shipments': [],
                'plantings': [],
                'warehouse_inventory': {},
                'total_cost_day': 0,
                'workday': self.workdays[day],
                'work_hours_used': 0
            }
            
            # Extract orders created on this day
            for v in self.providers:
                if self.variables['Y'][v][day].varValue and self.variables['Y'][v][day].varValue > 0.5:
                    order_details = []
                    order_cost = 0
                    for e in self.species:
                        if e in PROVIDER_COSTS[v]:
                            qty = self.variables['X'][e][v][day].varValue
                            if qty and qty > 0:
                                plant_cost = qty * (PROVIDER_COSTS[v][e] + TRANSPORT_COST_PER_PLANT)
                                order_cost += plant_cost
                                order_details.append({
                                    'species_id': e,
                                    'quantity': int(qty),
                                    'unit_cost': PROVIDER_COSTS[v][e],
                                    'transport_cost': qty * TRANSPORT_COST_PER_PLANT,
                                    'total_cost': plant_cost
                                })
                    
                    if order_details:
                        daily_data[day]['orders_created'].append({
                            'provider': v,
                            'species_quantities': order_details,
                            'total_cost': order_cost,
                            'arrival_day': day + ORDER_DELIVERY_TIME
                        })
                        daily_data[day]['total_cost_day'] += order_cost
            
            # Extract orders arriving on this day (created on day - ORDER_DELIVERY_TIME)
            if day > ORDER_DELIVERY_TIME:
                creation_day = day - ORDER_DELIVERY_TIME
                if creation_day in daily_data:
                    for order in daily_data[creation_day]['orders_created']:
                        daily_data[day]['orders_arrived'].append(order)
            
            # Extract shipments and plantings
            for p in self.planting_polygons:
                shipment_details = []
                total_plants = 0
                for e in self.species:
                    qty = self.variables['S'][e][p][day].varValue
                    if qty and qty > 0:
                        planting_cost = qty * PLANTATION_COST_PER_PLANT
                        shipment_details.append({
                            'species_id': e,
                            'quantity': int(qty),
                            'planting_cost': planting_cost
                        })
                        total_plants += int(qty)
                        daily_data[day]['total_cost_day'] += planting_cost
                
                if shipment_details:
                    trips = int(self.variables['N_trips'][p][day].varValue) if self.variables['N_trips'][p][day].varValue else 0
                    
                    # Calculate work hours used
                    travel_time = trips * 2 * TIME_DF.loc[self.warehouse_id, p]
                    
                    # Treatment time: Fixed time per species used (not per plant)
                    species_used = [s['species_id'] for s in shipment_details]
                    treatment_time = sum(self.treatment_times[e] for e in species_used)
                    
                    handling_time = total_plants * 2 * (LOAD_TIME_PER_PLANT + UNLOAD_TIME_PER_PLANT)
                    total_work_time = travel_time + treatment_time + handling_time
                    
                    daily_data[day]['work_hours_used'] += total_work_time
                    
                    shipment_data = {
                        'polygon_id': p,
                        'species_quantities': shipment_details,
                        'trips': trips,
                        'travel_time': travel_time,
                        'treatment_time': treatment_time,
                        'handling_time': handling_time,
                        'total_work_time': total_work_time,
                        'total_plants': total_plants
                    }
                    
                    daily_data[day]['shipments'].append(shipment_data)
                    daily_data[day]['plantings'].extend(shipment_details)
            
            # Extract warehouse inventory (simplified)
            for e in self.species:
                available = self.variables['InvDisp'][e][day].varValue
                in_acclimation = sum(
                    self.variables['InvAclim'][e][d][day].varValue or 0
                    for d in self.acclimation_stages
                )
                daily_data[day]['warehouse_inventory'][e] = {
                    'available': int(available) if available else 0,
                    'in_acclimation': int(in_acclimation) if in_acclimation else 0,
                    'total': int(available + in_acclimation) if (available and in_acclimation) else 0
                }
        
        return daily_data
    
    def save_results_to_files(self, base_filename: str = "mathematical_optimization"):
        """Save optimization results to files for analysis and comparison."""
        if self.model is None or self.model.status != pulp.LpStatusOptimal:
            logger.warning("No optimal solution to save")
            return
        
        import json
        from datetime import datetime
        
        # Use current timestamp for the summary data but fixed filenames
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save summary
        summary = {
            'model_type': 'mathematical_optimization',
            'timestamp': timestamp,
            'solve_time_seconds': self.solve_time,
            'polygons': self.planting_polygons,
            'time_horizon': self.time_horizon,
            'objective_type': self.objective_type,
            'status': self.solution_status,
            'objective_value': pulp.value(self.model.objective),
            'total_demand': int(self.demand.sum().sum()),
            'total_variables': len(self.model.variables()),
            'total_constraints': len(self.model.constraints)
        }
        
        summary_file = f"{base_filename}_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        logger.info(f"Summary saved to {summary_file}")
        
        # Save daily data
        daily_data = self.extract_daily_data()
        daily_file = f"{base_filename}_daily.json"
        with open(daily_file, 'w') as f:
            json.dump(daily_data, f, indent=2)
        logger.info(f"Daily data saved to {daily_file}")
        
        # Save solution details
        solution = self.extract_solution()
        solution_file = f"{base_filename}_solution.json"
        with open(solution_file, 'w') as f:
            json.dump(solution, f, indent=2)
        logger.info(f"Solution details saved to {solution_file}")
        
        return {
            'summary_file': summary_file,
            'daily_file': daily_file,
            'solution_file': solution_file
        }
    
    def print_performance_summary(self):
        """Print a comprehensive performance summary."""
        if self.model is None:
            print("No model to analyze")
            return
        
        print("\n" + "="*80)
        print("MATHEMATICAL OPTIMIZATION PERFORMANCE SUMMARY")
        print("="*80)
        
        print(f"Problem Size:")
        print(f"  Polygons: {len(self.planting_polygons)}")
        print(f"  Time Horizon: {self.time_horizon} days")
        print(f"  Total Demand: {int(self.demand.sum().sum()):,} plants")
        print(f"  Variables: {len(self.model.variables()):,}")
        print(f"  Constraints: {len(self.model.constraints):,}")
        
        print(f"\nComputational Performance:")
        print(f"  Solve Time: {self.solve_time:.2f} seconds")
        print(f"  Status: {self.solution_status}")
        
        if self.model.status == pulp.LpStatusOptimal:
            print(f"  Optimal Cost: ${pulp.value(self.model.objective):,.2f} MXN")
            
            # Calculate some efficiency metrics
            daily_data = self.extract_daily_data()
            total_work_hours = sum(day['work_hours_used'] for day in daily_data.values())
            workdays = sum(1 for day in daily_data.values() if day['workday'] and day['work_hours_used'] > 0)
            avg_daily_hours = total_work_hours / max(workdays, 1)
            
            print(f"\nOperational Efficiency:")
            print(f"  Total Work Hours: {total_work_hours:.1f} hours")
            print(f"  Active Work Days: {workdays}")
            print(f"  Average Daily Hours: {avg_daily_hours:.1f} hours")
            print(f"  Labor Utilization: {(avg_daily_hours/LABOR_TIME)*100:.1f}%")
            
            # Cost breakdown
            total_orders = sum(len(day['orders_created']) for day in daily_data.values())
            total_shipments = sum(len(day['shipments']) for day in daily_data.values())
            
            print(f"\nOperation Summary:")
            print(f"  Total Orders: {total_orders}")
            print(f"  Total Shipments: {total_shipments}")
            print(f"  Cost per Plant: ${pulp.value(self.model.objective)/int(self.demand.sum().sum()):.2f}")


def main():
    """Main function to solve the complete reforestation problem."""
    print("Starting Mathematical Optimization")
    print("="*80)
    
    # Use all polygons for complete problem (excluding warehouse)
    all_polygons = [i for i in range(1, 32) if i != BASE_ID]  # All 30 polygons except warehouse
    
    print(f"Solving complete problem:")
    print(f"  Polygons: {len(all_polygons)}")
    print(f"  Species: 10")
    print(f"  Providers: 3")
    
    # Create optimizer for complete problem
    optimizer = ReforestationOptimizer(
        selected_polygons=all_polygons,
        time_horizon=180,
        objective_type='cost'
    )
    
    # Diagnose potential issues
    print("\n--- DIAGNOSTIC PHASE ---")
    optimizer.diagnose_infeasibility()
    optimizer.diagnose_time_constraints()
    optimizer.suggest_parameter_adjustments()
    
    # Solve the optimization problem
    print("\n--- OPTIMIZATION PHASE ---")
    total_start_time = datetime.now()
    
    print("Building mathematical model...")
    optimizer.build_model()
    
    print(f"Model built successfully!")
    print(f"  Variables: {len(optimizer.model.variables()):,}")
    print(f"  Constraints: {len(optimizer.model.constraints):,}")
    
    print("\nStarting optimization...")
    
    # Use extended time limit for complete problem
    status = optimizer.solve(time_limit=18000)  # 5 hour limit
    
    total_end_time = datetime.now()
    total_time = (total_end_time - total_start_time).total_seconds()
    
    if status == pulp.LpStatusOptimal:
        print("\nSUCCESS: Mathematical optimization found optimal solution!")
        
        # Print detailed performance summary
        optimizer.print_performance_summary()
        
        # Save all results to files
        print(f"\n--- SAVING RESULTS ---")
        files_created = optimizer.save_results_to_files("mathematical_optimization")
        
        # Print detailed solution
        optimizer.print_solution()
        
        print(f"\n--- COMPARISON DATA ---")
        print(f"Total execution time: {total_time:.3f} seconds")
        print(f"Pure solve time: {optimizer.solve_time:.3f} seconds")
        print(f"Model building time: {total_time - optimizer.solve_time:.3f} seconds")
        
        # Extract and display sample daily data
        daily_data = optimizer.extract_daily_data()
        sample_days = [day for day in sorted(daily_data.keys()) 
                      if daily_data[day]['orders_created'] or daily_data[day]['shipments']][:5]
        
        if sample_days:
            print(f"\n--- SAMPLE DAILY ACTIVITIES ---")
            for day in sample_days:
                data = daily_data[day]
                print(f"Day {day} ({'Workday' if data['workday'] else 'Weekend'}):")
                if data['orders_created']:
                    print(f"  Orders: {len(data['orders_created'])} (${data['total_cost_day']:.2f})")
                if data['shipments']:
                    total_plants = sum(s['total_plants'] for s in data['shipments'])
                    print(f"  Shipments: {len(data['shipments'])} ({total_plants} plants, {data['work_hours_used']:.1f}h)")
        
        print(f"\nFiles saved:")
        for key, filename in files_created.items():
            print(f"  {key}: {filename}")
            
    else:
        print(f"\nOptimization failed with status: {pulp.LpStatus[status]}")
        print(f"Total time spent: {total_time:.3f} seconds")
        
        # Try with extended time horizon if it fails  
        print("\n--- RETRYING WITH EXTENDED TIME HORIZON ---")
        print("Attempting with longer time horizon...")
        
        optimizer_extended = ReforestationOptimizer(
            selected_polygons=all_polygons,
            time_horizon=365,  # Full year horizon
            objective_type='cost'
        )
        
        extended_start = datetime.now()
        optimizer_extended.build_model()
        print("Extended model built - attempting to solve...")
        status = optimizer_extended.solve(time_limit=36000)  # 10 hour limit
        extended_end = datetime.now()
        extended_time = (extended_end - extended_start).total_seconds()
        
        if status == pulp.LpStatusOptimal:
            print("SUCCESS: Extended model found optimal solution!")
            optimizer_extended.print_performance_summary()
            optimizer_extended.save_results_to_files("mathematical_optimization_extended")
        else:
            print(f"Extended model also failed with status: {pulp.LpStatus[status]}")
            print(f"Extended attempt time: {extended_time:.3f} seconds")
            print("Problem may require alternative solution approaches")
    
    print(f"\n--- NEXT STEPS FOR ANALYSIS ---")
    print(f"MODEL CHARACTERISTICS:")
    print(f"  1. {len(all_polygons)} polygons included")
    print(f"  2. Multiple variable types with interdependencies")
    print(f"  3. Comprehensive constraint categories")
    print(f"  4. Multi-objective optimization with penalties and rewards")
    print(f"  5. Extended time horizon (180-365 days)")
    print(f"  6. Vehicle fleet, workforce, quality, sustainability dimensions")
    print(f"")
    print(f"COMPARISON OPPORTUNITIES:")
    print(f"  1. Run heuristic with all polygons")
    print(f"  2. Compare computational times")
    print(f"  3. Analyze solution quality")
    print(f"  4. Evaluate scalability of exact vs heuristic methods")
    print(f"  5. Study practical applicability")


if __name__ == "__main__":
    main() 