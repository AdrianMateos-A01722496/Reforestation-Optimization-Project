from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from utils import (
    PLANTATION_COST_PER_PLANT, VAN_CAPACITY, WAREHOUSE_CAPACITY,
    MAX_PLANTS_ORDER_PER_PROVIDER_PER_DAY, ORDER_DELIVERY_TIME,
    TRANSPORT_COST_PER_PLANT, LOAD_TIME_PER_PLANT, UNLOAD_TIME_PER_PLANT,
    LABOR_TIME, MIN_ACCLIMATION_DAYS, BASE_ID,
    NORMAL_TREATMENT_HR_PER_PLANT, OPUNTIA_TREATMENT_HR_PER_PLANT,
    OPUNTIA_SPECIES_IDS, SPECIES_IDS, ALL_POLYGON_IDS, PLANTING_POLYGON_IDS,
    PROVIDER_COSTS, calculate_order_cost, get_treatment_time,
    calculate_planting_cost, calculate_transport_cost
)

@dataclass
class Order:
    order_day: int
    arrival_day: int
    amount_of_plants: int
    species_id_quantity: List[Tuple[int, int]]
    provider: str
    cost: float

@dataclass
class PlantingActivity:
    day: int
    polygon_id: int
    species_id: int
    quantity: int
    treatment_time: float  # in hours
    planting_cost: float
    trip_number: int = 1  # Trip number within the day

@dataclass
class TransportationActivity:
    day: int
    from_polygon: int
    to_polygon: int
    species_id: int
    quantity: int
    travel_time: float  # in hours
    load_time: float    # in hours
    unload_time: float  # in hours
    transport_cost: float

@dataclass
class DailyState:
    """Represents the state of the system on a given day"""
    day: int
    is_weekend: bool
    orders: List[Order]
    planting_activities: List[PlantingActivity]
    transportation_activities: List[TransportationActivity]
    warehouse_inventory: Dict[int, Dict[int, int]]  # stage -> {species_id -> quantity}
    daily_cost: float

@dataclass
class DailyRecord:
    """Represents detailed information about a single day's activities"""
    day: int
    date: datetime
    is_weekend: bool
    
    # Order information (if any)
    order_provider: Optional[str] = None
    order_species_quantities: List[Tuple[int, int]] = None  # List of (species_id, quantity)
    order_cost: float = 0.0
    
    # Warehouse inventory
    warehouse_inventory: Dict[int, Dict[int, int]] = None  # stage -> {species_id -> quantity}
    
    # Planting activities
    planting_activities: List[PlantingActivity] = None
    
    # Transportation activities
    transportation_activities: List[TransportationActivity] = None
    
    # Cost breakdown
    transport_cost: float = 0.0
    planting_cost: float = 0.0
    order_cost: float = 0.0
    total_cost: float = 0.0
    
    def __post_init__(self):
        if self.order_species_quantities is None:
            self.order_species_quantities = []
        if self.warehouse_inventory is None:
            self.warehouse_inventory = {
                0: {i: 0 for i in range(1, 11)},  # < 1 day
                1: {i: 0 for i in range(1, 11)},  # 1 day
                2: {i: 0 for i in range(1, 11)},  # 2 days
                3: {i: 0 for i in range(1, 11)}   # >= 3 days
            }
        if self.planting_activities is None:
            self.planting_activities = []
        if self.transportation_activities is None:
            self.transportation_activities = []
    
    def get_total_warehouse_inventory(self) -> int:
        """Get total number of plants in warehouse across all stages"""
        total = 0
        for stage in self.warehouse_inventory.values():
            total += sum(stage.values())
        return total
    
    def get_available_warehouse_space(self) -> int:
        """Get remaining warehouse capacity"""
        return WAREHOUSE_CAPACITY - self.get_total_warehouse_inventory()

class SupplyChainState:
    def __init__(self, start_date: datetime, demand: pd.DataFrame, time_matrix: pd.DataFrame):
        self.start_date = start_date
        self.current_day = 0
        self.remaining_labor_hours = 6  # 6-hour workday
        self.total_cost = 0
        
        # Initialize inventory tracking
        self.acclim_stage_0 = {i: 0 for i in range(1, 11)}  # < 1 day
        self.acclim_stage_1 = {i: 0 for i in range(1, 11)}  # 1 day
        self.acclim_stage_2 = {i: 0 for i in range(1, 11)}  # 2 days
        self.available_inventory = {i: 0 for i in range(1, 11)}  # >= 3 days
        
        # Initialize other state variables
        self.remaining_demand = demand.copy()
        self.time_matrix = time_matrix
        self.transportation_activities = []
        self.planting_activities = []
        self.orders = []  # Initialize orders list
        self.daily_records = []  # List of DailyRecord objects
        self._record_daily_state()  # Record initial state
        
        # Print initial state
        print(f"Starting optimization from {self.start_date.strftime('%Y-%m-%d')}")
    
    def get_total_warehouse_inventory(self) -> int:
        """Get total number of plants in warehouse across all stages"""
        total = 0
        for stage in [self.acclim_stage_0, self.acclim_stage_1, 
                     self.acclim_stage_2, self.available_inventory]:
            total += sum(stage.values())
        return total
    
    def get_available_warehouse_space(self) -> int:
        """Get remaining warehouse capacity"""
        return WAREHOUSE_CAPACITY - self.get_total_warehouse_inventory()
    
    def is_weekend(self, day: int) -> bool:
        """Check if a given day is a weekend"""
        date = self.start_date + timedelta(days=day)
        return date.weekday() >= 5  # 5 is Saturday, 6 is Sunday
    
    def get_current_date(self) -> datetime:
        """Get the current date based on start_date and current_day"""
        return self.start_date + timedelta(days=self.current_day)
    
    def advance_day(self):
        """Advance the simulation by one day"""
        # Record current state before advancing
        self._record_daily_state()
        
        # Move plants through acclimation stages
        for species_id in range(1, 11):
            self.available_inventory[species_id] += self.acclim_stage_2[species_id]
        
        self.acclim_stage_2 = self.acclim_stage_1.copy()
        self.acclim_stage_1 = self.acclim_stage_0.copy()
        self.acclim_stage_0 = {i: 0 for i in range(1, 11)}
        
        self.current_day += 1
        self.remaining_labor_hours = LABOR_TIME  # Reset labor hours for new day
        
        # Print progress every 10 days
        if self.current_day % 10 == 0:
            current_date = self.start_date + timedelta(days=self.current_day)
            print(f"Day {self.current_day}: {current_date.strftime('%Y-%m-%d')} - "
                  f"Remaining demand: {self.remaining_demand.sum().sum():,} plants")
    
    def _record_daily_state(self):
        """Record the state of the system for the current day"""
        # Create daily record
        daily_record = DailyRecord(
            day=self.current_day,
            date=self.get_current_date(),
            is_weekend=self.is_weekend(self.current_day),
            warehouse_inventory={
                0: self.acclim_stage_0.copy(),
                1: self.acclim_stage_1.copy(),
                2: self.acclim_stage_2.copy(),
                3: self.available_inventory.copy()
            }
        )
        
        # Record orders for this day
        day_orders = [o for o in self.orders if o.order_day == self.current_day]
        if day_orders:
            order = day_orders[0]  # We only allow one order per day
            daily_record.order_provider = order.provider
            daily_record.order_species_quantities = order.species_id_quantity
            daily_record.order_cost = order.cost
        
        # Record planting activities
        daily_record.planting_activities = [
            p for p in self.planting_activities if p.day == self.current_day
        ]
        daily_record.planting_cost = sum(p.planting_cost for p in daily_record.planting_activities)
        
        # Record transportation activities
        daily_record.transportation_activities = [
            t for t in self.transportation_activities if t.day == self.current_day
        ]
        daily_record.transport_cost = sum(t.transport_cost for t in daily_record.transportation_activities)
        
        # Calculate total cost for the day
        daily_record.total_cost = (
            daily_record.order_cost +
            daily_record.planting_cost +
            daily_record.transport_cost
        )
        
        self.daily_records.append(daily_record)

class OptimizationStrategy:
    """Base class for different optimization strategies"""
    def __init__(self, state: SupplyChainState):
        self.state = state
    
    def solve(self) -> SupplyChainState:
        """Implement the optimization strategy"""
        raise NotImplementedError("Subclasses must implement solve()")
    
    def evaluate_solution(self) -> float:
        """Evaluate the quality of the current solution"""
        raise NotImplementedError("Subclasses must implement evaluate_solution()") 