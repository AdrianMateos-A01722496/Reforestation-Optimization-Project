# Reforestation Optimization Project

## Problem Overview

This project addresses a complex reforestation optimization challenge involving 31 distinct polygons, 10 different plant species, and a multi-constraint supply chain system. The goal is to minimize total costs (planting, transportation, and plant purchasing) while meeting all demand requirements and operational constraints.

### Problem Context

- **Timeline**: Project begins September 1, 2025
- **Scope**: 31 polygons (excluding central base polygon ID 18)
- **Species**: 10 different plant species with varying costs and requirements
- **Objective**: Minimize total cost while satisfying all demand and constraints

### Key Challenge Features

#### Supply Chain Constraints
- **Warehouse capacity**: 10,000 plants maximum
- **Three suppliers**: moctezuma, venado, and laguna_seca
- **Order limits**: Maximum 8,000 plants per order, one order per day
- **Plant acclimation**: 3-day minimum acclimation period before planting
- **Transportation cost**: 0.5625 per plant from supplier to warehouse

#### Operational Constraints  
- **Labor hours**: 6 hours maximum per day
- **Weekend restrictions**: No planting on weekends (orders still allowed)
- **Vehicle capacity**: Single van with 524 plant capacity (exactly 1 hectare worth)
- **Pre-planting treatment**: 1 hour for normal species, 0.33 hours for opuntia species (5-8)
- **Planting cost**: 20 per plant regardless of species

#### Species-Specific Requirements
- **Proportional demand**: Same species ratios across all polygons
- **Provider specialization**: Each supplier offers different species at different costs
- **Treatment variation**: Opuntia species (5, 6, 7, 8) require less pre-planting treatment

## Project Structure

### Core Files

#### 1. `main.py` (Entry Point)
The main execution script that:
- Loads demand data from `data/encoded_demand.csv`
- Loads travel time matrix from `data/tiempos.csv`
- Initializes the supply chain state and optimization strategy
- Runs the optimization algorithm
- Generates comprehensive reports and visualizations
- Saves detailed state data for analysis

#### 2. `optimization_framework.py` (Core Classes)
Defines the fundamental data structures and base classes:

**Key Classes:**
- `Order`: Represents plant orders with supplier, species, quantities, and costs
- `PlantingActivity`: Records planting events with location, species, and timing
- `TransportationActivity`: Tracks vehicle movements and logistics
- `DailyStateRecord`: Captures daily metrics for analysis
- `SupplyChainState`: Central state management including inventory, orders, and constraints
- `OptimizationStrategy`: Abstract base class for optimization algorithms

#### 3. `polygon_strategy.py` (Current Algorithm)
Implements the primary optimization strategy:

**Core Methods:**
- `solve()`: Main optimization loop with safety limits and progress tracking
- `_get_next_polygon()`: Selects next polygon based on travel time from base
- `_calculate_max_plants_per_day()`: Calculates daily planting capacity per polygon
- `_order_plants_if_needed()`: Manages plant ordering with provider rotation
- `_plant_available_plants()`: Handles planting operations and logistics

**Key Features:**
- Provider rotation system (cycles through suppliers daily)
- Dynamic order sizing based on demand and inventory levels
- Progress tracking with infinite loop prevention
- Flexible planting logic for project completion

#### 4. `utils.py` (Constants and Utilities)
Contains all system constants and helper functions:

**Constants:**
- `VAN_CAPACITY = 524` (plants per trip)
- `WAREHOUSE_CAPACITY = 10000` (maximum storage)
- `LABOR_TIME = 6.0` (hours per day)
- `PLANTATION_COST_PER_PLANT = 20` (cost per plant)

**Provider-Species Mapping:**
```python
PROVIDER_COSTS = {
    "moctezuma": {3: 26, 4: 26, 5: 17, 7: 17, 9: 26.5, 10: 26},
    "venado": {4: 25, 5: 18, 6: 18, 7: 18, 8: 18},
    "laguna_seca": {1: 26, 2: 26, 3: 26, 6: 21, 7: 18}
}
```

**Species Proportions per Hectare:**
```python
SPECIES_PROPORTIONS = {
    1: 33,   # 6.30%
    2: 157,  # 29.96% (largest portion)
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

#### 5. `daily_data_collector.py` (Data Collection)
Collects and structures daily operational data for analysis and reporting:
- `collect_day_data()`: Captures comprehensive daily metrics
- `save_daily_data()`: Exports to JSON format for calendar generation

### Analysis and Visualization Files

#### 6. `create_calendar.py`
Generates interactive HTML calendar visualization showing daily activities, costs, and progress.

#### 7. `run_with_data_collection.py`
Extended main script that includes comprehensive data collection during optimization runs.

### Data Files

#### Input Data
- **`data/encoded_demand.csv`**: 31x10 matrix defining plant demand for each species in each polygon
- **`data/tiempos.csv`**: 31x31 travel time matrix between all polygons

#### Output Data
- **`reforestation_daily_data.json`**: Complete daily operational data
- **`state_data.json`**: Final state with all activities and costs
- **`detailed_state_log.csv`**: Tabular daily metrics for analysis
- **`reforestation_calendar.html`**: Interactive calendar visualization

### Development Files

#### 8. `demo.ipynb`
Jupyter notebook for:
- Interactive development and testing
- Data analysis and visualization
- Algorithm experimentation

## Installation and Setup

### Requirements
```bash
pip install -r requirements.txt
```

**Dependencies:**
- `pandas==2.2.1` - Data manipulation and analysis
- `numpy==1.26.4` - Numerical computations
- `plotly==5.19.0` - Interactive visualizations

### Quick Start

1. **Clone the repository:**
```bash
git clone <repository-url>
cd RetoOpti
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Run the optimization:**
```bash
python main.py
```

4. **View results:**
- Check console output for optimization progress
- Open `reforestation_calendar.html` in a browser for interactive visualization
- Analyze `detailed_state_log.csv` for daily metrics

## Algorithm Overview

### Current Strategy: PolygonStrategy

The current implementation uses a polygon-focused approach:

1. **Polygon Selection**: Chooses next polygon based on shortest travel time from base (polygon 18)

2. **Provider Rotation**: Cycles through suppliers daily:
   - Day 0: laguna_seca
   - Day 1: venado  
   - Day 2: moctezuma
   - Day 3: laguna_seca (repeats)

3. **Order Management**: 
   - Orders plants based on next polygon needs and current inventory
   - Prioritizes species needed for immediate planting
   - Respects warehouse capacity and daily order limits

4. **Planting Operations**:
   - Calculates daily planting capacity based on travel times
   - Plants available species when inventory and demand align
   - Handles mixed species loads and partial van trips

### Key Optimizations

#### Warehouse Management
Maintains optimal species distribution:
```python
WAREHOUSE_PROPORTIONS = {
    1: 630,   2: 2996,  3: 630,   4: 630,   5: 744,
    6: 573,   7: 1107,  8: 973,   9: 1317,  10: 401
}
```

#### Provider Specialization
Each supplier optimized for specific species:
- **laguna_seca**: Species 1, 2, 3, 6, 7
- **venado**: Species 4, 5, 6, 7, 8  
- **moctezuma**: Species 3, 4, 5, 7, 9, 10

## Recent Improvements

### Bug Fixes and Enhancements

1. **Infinite Loop Prevention**: Added safety limits and progress tracking
2. **Provider Rotation**: Implemented systematic supplier cycling
3. **Cost Optimization**: Fixed provider-species mapping for better cost efficiency
4. **Flexible Planting**: Enhanced logic for partial loads and project completion
5. **Progress Reporting**: Added detailed progress tracking and completion metrics

### Performance Results

Latest optimization run achieved:
- **Demand Reduction**: From ~95,000 to 76,490 plants
- **Provider Utilization**: All 3 providers being used effectively
- **Species Coverage**: All 10 species being ordered appropriately
- **Algorithm Stability**: No infinite loops, controlled execution

## Usage Examples

### Basic Optimization Run
```bash
python main.py
```

### With Data Collection
```bash
python run_with_data_collection.py
```

### Interactive Development
```bash
jupyter notebook demo.ipynb
```

## Output Analysis

### Key Metrics
- **Total Cost**: Sum of plant, transportation, and planting costs
- **Project Duration**: Days needed to complete all planting
- **Resource Utilization**: Warehouse, labor, and vehicle efficiency
- **Species Distribution**: Balance across all required species

### Visualization Features
- **Interactive Calendar**: Daily activities and progress
- **Cost Breakdown**: Detailed expense analysis
- **Progress Tracking**: Demand reduction over time
- **Resource Usage**: Warehouse and labor utilization

## Future Enhancements

### Priority Areas
1. **Proportional Planting**: Implement simultaneous multi-species planting
2. **Advanced Scheduling**: Optimize planting sequences across polygons
3. **Cost Optimization**: Fine-tune provider selection and order timing
4. **Constraint Handling**: Better weekend and labor hour management

### Potential Improvements
- Machine learning-based polygon prioritization
- Dynamic provider selection based on real-time costs
- Advanced inventory management strategies
- Multi-objective optimization (cost vs. time)

## Contributing

When contributing to this project:
1. **Follow naming conventions**: Use clear, descriptive variable names
2. **Maintain documentation**: Update README for any structural changes
3. **Test thoroughly**: Ensure changes don't break existing functionality
4. **Avoid notebook modifications**: Don't edit .ipynb files directly
5. **Keep comments concise**: Use short, clear code comments

## License

This project is developed for reforestation optimization research and planning purposes. 