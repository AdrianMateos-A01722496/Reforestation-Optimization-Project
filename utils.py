from typing import Dict, List, Tuple
import pandas as pd

# Constants
PLANTATION_COST_PER_PLANT = 20.0
VAN_CAPACITY = 524
WAREHOUSE_CAPACITY = 10000
MAX_PLANTS_ORDER_PER_PROVIDER_PER_DAY = 8000
ORDER_DELIVERY_TIME = 1
TRANSPORT_COST_PER_PLANT = 0.5625
LOAD_TIME_PER_PLANT = 0.5 / VAN_CAPACITY
UNLOAD_TIME_PER_PLANT = 0.5 / VAN_CAPACITY
LABOR_TIME = 6
MIN_ACCLIMATION_DAYS = 3
BASE_ID = 18
NORMAL_TREATMENT_HR_PER_PLANT = 1
OPUNTIA_TREATMENT_HR_PER_PLANT = 1/3
OPUNTIA_SPECIES_IDS = [5, 6, 7, 8]
SPECIES_IDS = list(range(1, 11))
ALL_POLYGON_IDS = list(range(1, 32))
PLANTING_POLYGON_IDS = [p for p in ALL_POLYGON_IDS if p != BASE_ID]

# Provider costs
PROVIDER_COSTS = {
    "moctezuma": {3: 26, 4: 26, 5:17, 7:17, 9: 26.5, 10: 26},
    "venado": {4: 25, 5:18, 6:18, 7:18, 8:18},
    "laguna_seca": {1: 26, 2: 26, 3: 26, 6: 21, 7: 18}
}

# Species proportions (plants per hectare)
SPECIES_PROPORTIONS = {
    1: 33,   # 6.30%
    2: 157,  # 29.96%
    3: 33,   # 6.30%
    4: 33,   # 6.30%
    5: 39,   # 7.44%
    6: 30,   # 5.73%
    7: 58,   # 11.07%
    8: 51,   # 9.73%
    9: 69,   # 13.17%
    10: 21   # 4.01%
}

# Ideal warehouse proportions (for 10000 plants)
WAREHOUSE_PROPORTIONS = {
    1: 630,   # 6.30%
    2: 2996,  # 29.96%
    3: 630,   # 6.30%
    4: 630,   # 6.30%
    5: 744,   # 7.44%
    6: 573,   # 5.73%
    7: 1107,  # 11.07%
    8: 973,   # 9.73%
    9: 1317,  # 13.17%
    10: 400   # 4.00%
}

# This is the ideal species to buy from each provider
PROVIDER_SPECIES = {
    'laguna_seca': [1, 2, 3, 6, 7],
    'venado': [4, 5, 6, 7, 8],
    'moctezuma': [3, 4, 5, 7, 9, 10]
}

def calculate_order_cost(order) -> float:
    """Calculate total cost of an order including transport"""
    cost = 0
    try:
        for species_id, quantity in order.species_id_quantity:
            cost += quantity * PROVIDER_COSTS[order.provider][species_id]
            cost += quantity * TRANSPORT_COST_PER_PLANT
        return cost
    except KeyError as e:
        print(f"Warning: Provider '{order.provider}' does not supply species {species_id}.")
        return 0

def get_treatment_time(species_id: int, quantity: int) -> float:
    """Calculate treatment time for a given species (constant regardless of quantity since all plants can be submerged simultaneously)"""
    if species_id in OPUNTIA_SPECIES_IDS:
        return OPUNTIA_TREATMENT_HR_PER_PLANT  # 0.33 hours (20 minutes)
    return NORMAL_TREATMENT_HR_PER_PLANT  # 1 hour

def calculate_planting_cost(quantity: int) -> float:
    """Calculate cost of planting a given quantity of plants"""
    return quantity * PLANTATION_COST_PER_PLANT

def calculate_transport_cost(quantity: int) -> float:
    """Calculate transport cost for a given quantity of plants"""
    return quantity * TRANSPORT_COST_PER_PLANT

def calculate_total_activity_time(
    travel_time: float,
    quantity: int,
    species_id: int
) -> float:
    """Calculate total time needed for a transportation activity"""
    treatment_time = get_treatment_time(species_id, quantity)
    load_time = quantity * LOAD_TIME_PER_PLANT
    unload_time = quantity * UNLOAD_TIME_PER_PLANT
    return travel_time + treatment_time + load_time + unload_time

def check_labor_hours_constraint(activities: List, day: int) -> bool:
    """Check if total activity time for a day exceeds labor hours"""
    total_time = sum(
        calculate_total_activity_time(
            activity.travel_time,
            activity.quantity,
            activity.species_id
        )
        for activity in activities
        if activity.day == day
    )
    return total_time <= LABOR_TIME

def get_available_providers_for_species(species_id: int) -> List[str]:
    """Get list of providers that can supply a given species"""
    return [
        provider for provider, species_costs in PROVIDER_COSTS.items()
        if species_id in species_costs
    ]

def get_cheapest_provider_for_species(species_id: int) -> Tuple[str, float]:
    """Get the provider with lowest cost for a given species"""
    available_providers = get_available_providers_for_species(species_id)
    if not available_providers:
        return None, float('inf')
    
    provider_costs = [
        (provider, PROVIDER_COSTS[provider][species_id])
        for provider in available_providers
    ]
    return min(provider_costs, key=lambda x: x[1])