"""
Mathematical Model for Reforestation Supply Chain Optimization

This module implements the complete mathematical model using PuLP for the 
reforestation optimization problem as defined in mathematical_model_summary.md.
"""

import pulp as pl
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from utils import (
    PLANTATION_COST_PER_PLANT, VAN_CAPACITY, WAREHOUSE_CAPACITY,
    MAX_PLANTS_ORDER_PER_PROVIDER_PER_DAY, ORDER_DELIVERY_TIME,
    TRANSPORT_COST_PER_PLANT, LOAD_TIME_PER_PLANT, UNLOAD_TIME_PER_PLANT,
    LABOR_TIME, MIN_ACCLIMATION_DAYS, BASE_ID,
    NORMAL_TREATMENT_HR_PER_PLANT, OPUNTIA_TREATMENT_HR_PER_PLANT,
    OPUNTIA_SPECIES_IDS, SPECIES_IDS, ALL_POLYGON_IDS, PLANTING_POLYGON_IDS,
    PROVIDER_COSTS, DEMAND_DF, TIME_DF, get_treatment_time
)

class MathematicalOptimizationModel:
    """
    Complete mathematical model implementation for reforestation optimization
    using Mixed Integer Programming with PuLP.
    """
    
    def __init__(self, max_days: int = 365, start_date: datetime = None):
        """
        Initialize the mathematical optimization model.
        
        Args:
            max_days: Maximum number of days to consider in optimization
            start_date: Project start date (defaults to Sept 1, 2025)
        """
        self.max_days = max_days
        self.start_date = start_date or datetime(2025, 9, 1)
        
        # Define sets
        self.P = ALL_POLYGON_IDS  # All polygons {1, ..., 31}
        self.P_siembra = PLANTING_POLYGON_IDS  # Planting polygons (excluding 18)
        self.E = SPECIES_IDS  # Species {1, ..., 10}
        self.V = list(PROVIDER_COSTS.keys())  # Providers
        self.T = list(range(1, max_days + 1))  # Time periods
        self.D_aclim = [0, 1, 2]  # Acclimatization stages
        
        # Initialize parameters
        self._initialize_parameters()
        
        # Create the optimization problem
        self.model = pl.LpProblem("Reforestation_Optimization", pl.LpMinimize)
        
        # Create decision variables
        self._create_decision_variables()
        
        # Add constraints
        self._add_constraints()
        
        # Set objective function
        self._set_objective()
        
    def _initialize_parameters(self):
        """Initialize all model parameters from data files and constants."""
        
        # Demand matrix
        self.demand = {}
        for p in self.P_siembra:
            for e in self.E:
                self.demand[p, e] = DEMAND_DF.loc[p, e]
        
        # Time matrix
        self.travel_time = {}
        for p1 in self.P:
            for p2 in self.P:
                self.travel_time[p1, p2] = TIME_DF.loc[p1, p2]
        
        # Capacity parameters
        self.cap_almacen = WAREHOUSE_CAPACITY
        self.cap_camioneta = VAN_CAPACITY
        self.max_pedido_vivero = MAX_PLANTS_ORDER_PER_PROVIDER_PER_DAY
        
        # Cost parameters
        self.c_plantacion = PLANTATION_COST_PER_PLANT
        self.c_transporte_planta_vivero = TRANSPORT_COST_PER_PLANT
        
        # Purchase costs by provider and species
        self.c_compra = {}
        for v in self.V:
            for e in self.E:
                if e in PROVIDER_COSTS[v]:
                    self.c_compra[e, v] = PROVIDER_COSTS[v][e]
                else:
                    self.c_compra[e, v] = float('inf')  # Cannot supply
        
        # Time parameters
        self.t_entrega_vivero = ORDER_DELIVERY_TIME
        self.t_aclim_min = MIN_ACCLIMATION_DAYS
        self.h_jornada = LABOR_TIME
        
        # Treatment times
        self.t_tratamiento = {}
        for e in self.E:
            self.t_tratamiento[e] = get_treatment_time(e, 1)
        
        # Load/unload time per plant (includes both loading AND unloading)
        self.t_carga_descarga_planta = 2 * (LOAD_TIME_PER_PLANT + UNLOAD_TIME_PER_PLANT)
        
        # Workday indicator
        self.dia_laborable = {}
        for t in self.T:
            date = self.start_date + timedelta(days=t-1)
            self.dia_laborable[t] = 1 if date.weekday() < 5 else 0  # Mon-Fri = 1, Sat-Sun = 0
        
        # Big M for logical constraints
        self.M = 100000
        
    def _create_decision_variables(self):
        """Create all decision variables for the model."""
        
        # Order variables
        self.X = {}  # X_e,v,t: Quantity of species e ordered from provider v on day t
        for e in self.E:
            for v in self.V:
                for t in self.T:
                    if self.c_compra[e, v] < float('inf'):  # Only if provider supplies species
                        self.X[e, v, t] = pl.LpVariable(f"X_{e}_{v}_{t}", 
                                                      lowBound=0, cat='Integer')
                    else:
                        self.X[e, v, t] = pl.LpVariable(f"X_{e}_{v}_{t}", 
                                                      lowBound=0, upBound=0, cat='Integer')
        
        # Binary order indicator
        self.Y = {}  # Y_v,t: 1 if order placed to provider v on day t
        for v in self.V:
            for t in self.T:
                self.Y[v, t] = pl.LpVariable(f"Y_{v}_{t}", cat='Binary')
        
        # Inventory variables
        self.InvAclim = {}  # InvAclim_e,d,t: Inventory in acclimatization stage d
        for e in self.E:
            for d in self.D_aclim:
                for t in self.T:
                    self.InvAclim[e, d, t] = pl.LpVariable(f"InvAclim_{e}_{d}_{t}", 
                                                         lowBound=0, cat='Integer')
        
        self.InvDisp = {}  # InvDisp_e,t: Available inventory
        for e in self.E:
            for t in self.T:
                self.InvDisp[e, t] = pl.LpVariable(f"InvDisp_{e}_{t}", 
                                                 lowBound=0, cat='Integer')
        
        # Shipment variables
        self.S = {}  # S_e,p,t: Quantity shipped to polygon p
        for e in self.E:
            for p in self.P_siembra:
                for t in self.T:
                    self.S[e, p, t] = pl.LpVariable(f"S_{e}_{p}_{t}", 
                                                  lowBound=0, cat='Integer')
        
        # Trip variables
        self.N_viajes = {}  # N_viajes_p,t: Number of trips to polygon p
        for p in self.P_siembra:
            for t in self.T:
                self.N_viajes[p, t] = pl.LpVariable(f"N_viajes_{p}_{t}", 
                                                  lowBound=0, cat='Integer')
        
        # Planting variables
        self.Plantado = {}  # Plantado_e,p,t: Quantity planted
        for e in self.E:
            for p in self.P_siembra:
                for t in self.T:
                    self.Plantado[e, p, t] = pl.LpVariable(f"Plantado_{e}_{p}_{t}", 
                                                         lowBound=0, cat='Integer')
        
        # Final day variable
        self.T_final = pl.LpVariable("T_final", lowBound=1, upBound=self.max_days, cat='Integer')
        
    def _add_constraints(self):
        """Add all constraints to the model."""
        
        # Constraint 1: Max quantity per order
        for v in self.V:
            for t in self.T:
                self.model += (
                    pl.lpSum([self.X[e, v, t] for e in self.E]) <= 
                    self.max_pedido_vivero * self.Y[v, t],
                    f"MaxQuantityPerOrder_{v}_{t}"
                )
        
        # Constraint 2: Plant arrivals & start of acclimatization
        for e in self.E:
            for t in self.T:
                if t > self.t_entrega_vivero:
                    arrival_sum = pl.lpSum([self.X[e, v, t - self.t_entrega_vivero] 
                                          for v in self.V])
                    self.model += (
                        self.InvAclim[e, 0, t] == arrival_sum,
                        f"PlantArrivals_{e}_{t}"
                    )
                else:
                    self.model += (
                        self.InvAclim[e, 0, t] == 0,
                        f"PlantArrivals_{e}_{t}"
                    )
        
        # Constraint 3: Acclimatization flow
        for e in self.E:
            for d in [1, 2]:
                for t in self.T:
                    if t > 1:
                        self.model += (
                            self.InvAclim[e, d, t] == self.InvAclim[e, d-1, t-1],
                            f"AcclimatizationFlow_{e}_{d}_{t}"
                        )
                    else:
                        self.model += (
                            self.InvAclim[e, d, t] == 0,
                            f"AcclimatizationFlow_{e}_{d}_{t}"
                        )
        
        # Constraint 4: Available inventory balance
        for e in self.E:
            for t in self.T:
                if t == 1:
                    # For day 1, no previous inventory
                    shipments = pl.lpSum([self.S[e, p, t] for p in self.P_siembra])
                    self.model += (
                        self.InvDisp[e, t] == 0 - shipments,
                        f"InventoryBalance_{e}_{t}"
                    )
                else:
                    # For days > 1, include previous inventory
                    prev_available = self.InvDisp[e, t-1]
                    prev_completed = self.InvAclim[e, 2, t-1]
                    shipments = pl.lpSum([self.S[e, p, t] for p in self.P_siembra])
                    
                    self.model += (
                        self.InvDisp[e, t] == prev_available + prev_completed - shipments,
                        f"InventoryBalance_{e}_{t}"
                    )
        
        # Constraint 5: Warehouse capacity
        for t in self.T:
            total_inventory = pl.lpSum([
                self.InvDisp[e, t] + 
                pl.lpSum([self.InvAclim[e, d, t] for d in self.D_aclim])
                for e in self.E
            ])
            self.model += (
                total_inventory <= self.cap_almacen,
                f"WarehouseCapacity_{t}"
            )
        
        # Constraint 6: Demand fulfillment
        for e in self.E:
            for p in self.P_siembra:
                total_planted = pl.lpSum([self.Plantado[e, p, t] for t in self.T])
                self.model += (
                    total_planted == self.demand[p, e],
                    f"DemandFulfillment_{e}_{p}"
                )
        
        # Constraint 7: Planting logic
        for e in self.E:
            for p in self.P_siembra:
                for t in self.T:
                    self.model += (
                        self.Plantado[e, p, t] == self.S[e, p, t],
                        f"PlantingLogic_{e}_{p}_{t}"
                    )
        
        # Constraint 8: Internal transport capacity
        for p in self.P_siembra:
            for t in self.T:
                total_shipped = pl.lpSum([self.S[e, p, t] for e in self.E])
                self.model += (
                    total_shipped <= self.N_viajes[p, t] * self.cap_camioneta,
                    f"TransportCapacity_{p}_{t}"
                )
        
        # Constraint 9: Workday restrictions
        for e in self.E:
            for p in self.P_siembra:
                for t in self.T:
                    self.model += (
                        self.S[e, p, t] <= self.M * self.dia_laborable[t],
                        f"WorkdayRestriction_S_{e}_{p}_{t}"
                    )
        
        for p in self.P_siembra:
            for t in self.T:
                self.model += (
                    self.N_viajes[p, t] <= self.M * self.dia_laborable[t],
                    f"WorkdayRestriction_N_{p}_{t}"
                )
        
        # Constraint 10: Daily work hour limit
        for t in self.T:
            if self.dia_laborable[t] == 1:  # Only for workdays
                # Treatment time
                treatment_time = pl.lpSum([
                    self.S[e, p, t] * self.t_tratamiento[e]
                    for p in self.P_siembra for e in self.E
                ])
                
                # Loading/unloading time
                loading_time = pl.lpSum([
                    self.S[e, p, t] * self.t_carga_descarga_planta
                    for p in self.P_siembra for e in self.E
                ])
                
                # Travel time (round trip)
                travel_time = pl.lpSum([
                    self.N_viajes[p, t] * 2 * self.travel_time[BASE_ID, p]
                    for p in self.P_siembra
                ])
                
                total_time = treatment_time + loading_time + travel_time
                
                self.model += (
                    total_time <= self.h_jornada,
                    f"DailyWorkHourLimit_{t}"
                )
        
        # Additional constraint: T_final definition using big M method
        for t in self.T:
            # Create binary indicator for activity on day t
            activity_indicator = pl.LpVariable(f"ActivityIndicator_{t}", cat='Binary')
            
            # Activity sum for day t
            activities = (
                pl.lpSum([self.X[e, v, t] for e in self.E for v in self.V]) +
                pl.lpSum([self.S[e, p, t] for e in self.E for p in self.P_siembra])
            )
            
            # If activities > 0, then activity_indicator = 1
            self.model += (
                activities <= self.M * activity_indicator,
                f"ActivityIndicator1_{t}"
            )
            
            # If activity_indicator = 1, then T_final >= t
            self.model += (
                self.T_final >= t * activity_indicator,
                f"FinalDayDefinition_{t}"
            )
    
    def _set_objective(self):
        """Set the objective function to minimize total cost."""
        
        # Purchase and transport costs
        purchase_cost = pl.lpSum([
            self.X[e, v, t] * (self.c_compra[e, v] + self.c_transporte_planta_vivero)
            for e in self.E for v in self.V for t in self.T
            if self.c_compra[e, v] < float('inf')
        ])
        
        # Planting costs
        planting_cost = pl.lpSum([
            self.Plantado[e, p, t] * self.c_plantacion
            for e in self.E for p in self.P_siembra for t in self.T
        ])
        
        # Total cost objective
        total_cost = purchase_cost + planting_cost
        
        self.model += total_cost, "Total_Cost"
    
    def solve(self, solver=None, time_limit=None, gap_tolerance=None):
        """
        Solve the optimization model.
        
        Args:
            solver: PuLP solver to use (default: PULP_CBC_CMD)
            time_limit: Maximum solving time in seconds
            gap_tolerance: MIP gap tolerance (e.g., 0.01 for 1%)
            
        Returns:
            Solution status and results
        """
        if solver is None:
            solver = pl.PULP_CBC_CMD(msg=1)
            if time_limit:
                solver.timeLimit = time_limit
            if gap_tolerance:
                solver.optimalityTolerance = gap_tolerance
        
        print("Starting optimization...")
        print(f"Model statistics:")
        print(f"  Variables: {len(self.model.variables())}")
        print(f"  Constraints: {len(self.model.constraints)}")
        
        # Solve the model
        self.model.solve(solver)
        
        # Check solution status
        status = pl.LpStatus[self.model.status]
        print(f"Solution status: {status}")
        
        if self.model.status == pl.LpStatusOptimal:
            print(f"Optimal solution found!")
            print(f"Total cost: ${pl.value(self.model.objective):,.2f}")
            if self.T_final.varValue:
                print(f"Project duration: {int(self.T_final.varValue)} days")
            return self._extract_solution()
        elif self.model.status == pl.LpStatusInfeasible:
            print("Problem is infeasible!")
            return None
        else:
            print(f"Solver terminated with status: {status}")
            return None
    
    def _extract_solution(self):
        """Extract and organize solution results."""
        solution = {
            'status': pl.LpStatus[self.model.status],
            'total_cost': pl.value(self.model.objective),
            'project_duration': int(self.T_final.varValue) if self.T_final.varValue else None,
            'orders': [],
            'daily_activities': {},
            'inventory_levels': {}
        }
        
        # Extract orders
        for e in self.E:
            for v in self.V:
                for t in self.T:
                    if self.X[e, v, t].varValue and self.X[e, v, t].varValue > 0:
                        solution['orders'].append({
                            'day': t,
                            'provider': v,
                            'species': e,
                            'quantity': int(self.X[e, v, t].varValue)
                        })
        
        # Extract daily activities
        for t in self.T:
            solution['daily_activities'][t] = {
                'planting': [],
                'trips': {}
            }
            
            # Planting activities
            for e in self.E:
                for p in self.P_siembra:
                    if self.Plantado[e, p, t].varValue and self.Plantado[e, p, t].varValue > 0:
                        solution['daily_activities'][t]['planting'].append({
                            'polygon': p,
                            'species': e,
                            'quantity': int(self.Plantado[e, p, t].varValue)
                        })
            
            # Trip information
            for p in self.P_siembra:
                if self.N_viajes[p, t].varValue and self.N_viajes[p, t].varValue > 0:
                    solution['daily_activities'][t]['trips'][p] = int(self.N_viajes[p, t].varValue)
        
        # Extract inventory levels
        for t in self.T:
            solution['inventory_levels'][t] = {
                'available': {},
                'acclimatizing': {d: {} for d in self.D_aclim}
            }
            
            for e in self.E:
                if self.InvDisp[e, t].varValue:
                    solution['inventory_levels'][t]['available'][e] = int(self.InvDisp[e, t].varValue)
                
                for d in self.D_aclim:
                    if self.InvAclim[e, d, t].varValue:
                        solution['inventory_levels'][t]['acclimatizing'][d][e] = int(self.InvAclim[e, d, t].varValue)
        
        return solution

def create_and_solve_model(max_days: int = 365, time_limit: int = 3600):
    """
    Create and solve the mathematical optimization model.
    
    Args:
        max_days: Maximum days for optimization horizon
        time_limit: Solver time limit in seconds
        
    Returns:
        Optimization results
    """
    model = MathematicalOptimizationModel(max_days=max_days)
    results = model.solve(time_limit=time_limit)
    return model, results

if __name__ == "__main__":
    # Example usage
    print("Creating and solving reforestation optimization model...")
    model, results = create_and_solve_model(max_days=400, time_limit=1800)
    
    if results:
        print("\nSolution Summary:")
        print(f"Total Cost: ${results['total_cost']:,.2f}")
        print(f"Project Duration: {results['project_duration']} days")
        print(f"Number of Orders: {len(results['orders'])}")
        
        # Display first few orders
        print("\nFirst 5 Orders:")
        for order in results['orders'][:5]:
            print(f"  Day {order['day']}: {order['quantity']} plants of species {order['species']} from {order['provider']}")
    else:
        print("No solution found!") 