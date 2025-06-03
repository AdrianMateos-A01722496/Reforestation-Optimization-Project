# Reforestation Optimization Problem

## Problem Overview

The goal is to optimize a reforestation project across 31 distinct polygons using 10 different plant species. The project aims to minimize total costs (planting, transportation, and plant purchase) while adhering to various constraints. The project begins on September 1, 2025.

## Key Constraints

### Planting Constraints

- Plants must be planted in specific polygons (excluding central base polygon, ID 18 which has no demand)
- Demand for each species in each polygon is predefined in a csv, each row is a polygon (1-31) and each column is a species (1-10) spreadsheet is in `data/encoded_demand.csv`
- The proportion of the demand is the same across all polygons, this simplifies the problem a little bit, since by knowing this we can avoid ordering too many or too little plants of a certain species.
- There's a pre-planting constraint, normal species need to be submerged in water for 1 hour, however opuntia species (species numbers 5, 6, 7, 8) only need to be sumberged for 20 minutes so 0.33 hrs.
- Labor time is limited to only 6 hours per day.
- No planting on weekends (Saturday, Sunday), however we can place orders on those days and those days do count towards the acclimatization constraints we mention later on.
- The cost for putting each individual plant in the ground is 20 per plant. No matter the species.

### Transportation inside reforestation area.

- We have a Single vehicle (van) with maximum capacity of 524 plants (exactly the amount of plants that fit on 1 hectare).
- Travel times between polygons defined in `data/tiempos.csv`
- Loading/unloading times per plant is 0.5 hrs / 524. So loading/unloading the truck at full capacity would take 0.5 hrs.
- There is no transportation cost for transportation within the 31 polygons.
- Additional info: the areas in hectares of each of the polygons are in this list. (polygon 18 has area 0 because it has no demand).
- Areas = [5.4, 7.52, 8, 8, 7.56, 4.19, 6.28, 7.6, 8, 8, 7.67, 1.47, 7.97, 5.98, 5.4, 5.64, 6.11, 0, 4.92, 1.38, 8, 7.82, 5.53, 5.64, 5.05, 4.75, 1.28, 6.64, 6.54, 6.76, 7.34]

### Warehouse & Ordering Constraints

- Warehouse is located at Polygon 18.
- Three providers: "moctezuma," "venado," and "laguna_seca"
- Provider-specific species costs:
- PROVIDER_COSTS = {"moctezuma": {3: 26, 4: 26, 5:17, 7:17, 9: 26.5, 10: 26}, "venado": {4: 25, 5:18, 6:18, 7:18, 8:18}, "laguna_seca": {1: 26, 2: 26, 3: 26, 6: 21, 7: 18}}
- Orders arrive following day after making the order.
- Maximum order: 8,000 plants.
- We can only make one order per day (only from one provider).
- Apart from the actual cost of the plants we have a transportation cost, to take the plants from the providers to the warehouse. This cost is equal to 0.5625 per plant. So for a full delivery of a maximum order of 8000 plants from one of the suppliers to polygon 18 the transportation cost would be 4500.
- Warehouse capacity: 10,000 plants.
- Plants need to go through an acclimatization process in which they acclimatize for AT LEAST 3 days before they can be planted, we handle it this way:
  - Day 0: Arrive (acclim_stage_0)
  - Day 1: Move to acclim_stage_1
  - Day 2: Move to acclim_stage_2
  - Day 3: Available for planting

## Code Structure

### 1. `main.py`

- Main script to run optimization
- Loads demand data and time matrix
- Initializes state and strategy
- Generates reports and saves state data

### 2. `optimization_framework.py`

Core classes:

- `Order`: Plant order representation
- `PlantingActivity`: Planting event
- `TransportationActivity`: Transportation event
- `DailyStateRecord`: Daily metrics
- `SupplyChainState`: Overall simulation state
- `OptimizationStrategy`: Base strategy class

### 3. `polygon_strategy.py`

Current implementation:

- `solve()`: Main optimization loop
- `_get_next_polygon()`: Next polygon selection
- `_calculate_max_plants_per_day()`: Daily planting capacity
- `_order_plants_if_needed()`: Order management
- `_plant_available_plants()`: Planting process

### 4. `utils.py`

Constants and utilities:

- System constants (capacities, costs, times)
- Helper functions for calculations
- Species proportions and provider mappings
- Cost calculation functions

### 5. `visualization.py`

Output processing:

- `save_state_data()`: Detailed daily log
- `generate_summary_report()`: Overall results

## Key Learnings

### Provider Specialization

Optimal provider-species relationships:

- 'laguna_seca': Species 1, 2, 3
- 'venado': Species 4, 6, 8
- 'moctezuma': Species 5, 7, 9, 10

### Warehouse Proportions

Ideal species distribution for 10,000 plant capacity:

```python
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
    10: 401   # 4.01%
}
```

### Species Proportions

Plants per hectare for each species:

```python
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
```

## Current Challenges

The `PolygonStrategy` is experiencing issues:

1. Getting stuck ordering only Species 2 from 'laguna_seca'
2. Not planting available plants
3. Not making progress in reducing demand

Key areas needing attention:

1. Ordering logic to maintain balanced species mix
2. Planting logic to utilize available inventory
3. Progress tracking and optimization

## Next Steps

1. Debug ordering logic to ensure balanced species orders
2. Fix planting logic to effectively use available plants
3. Implement better progress tracking
4. Optimize the strategy for cost efficiency
