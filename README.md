# Reforestation Optimization Project

## Problem Overview

This project addresses a complex reforestation optimization challenge involving 31 distinct polygons, 10 different plant species, and a multi-constraint supply chain system. The goal is to minimize total costs (planting, transportation, and plant purchasing) while meeting all demand requirements and operational constraints.

### Performance Results

**Latest optimization run achieved remarkable success:**
- **Project Completion**: 100% - All demand satisfied successfully
- **Total Cost**: $4,206,338.44
- **Project Duration**: 170 days
- **Provider Utilization**: All 3 providers used systematically
- **Species Coverage**: All 10 species ordered from correct providers
- **Algorithm Stability**: Zero infinite loops, controlled execution
- **Final Inventory**: 1,459 plants remaining in warehouse

### Problem Context

- **Timeline**: Project begins September 1, 2025.
- **Scope**: 31 polygons
- **Species**: 10 different plant species with varying costs and requirements
- **Objective**: Minimize total cost while satisfying all demand and constraints

### Key Challenge Features

#### Supply Chain Constraints
- **Warehouse capacity**: 10,000 plants maximum.
- **Three suppliers**: Moctezuma, Venado, and Laguna Seca.
- **Order limits**: Maximum $8,000 plants per order, one order per day.
- **Plant acclimation**: 3-day minimum acclimation period before planting.
- **Transportation cost**: $0.5625 per plant from supplier to warehouse.

#### Operational Constraints  
- **Labor hours**: 6 hours maximum per day
- **Weekend restrictions**: No planting on weekends (orders still allowed)
- **Vehicle capacity**: Single van with 524 plant capacity (exactly 1 hectare worth)
- **Pre-planting treatment**: 1 hour for normal species, 0.33 hours (20 mins) for opuntia species (5-8)
- **Planting cost**: $20 per plant regardless of species

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
- Runs the optimization algorithm with progress tracking
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

#### 3. `polygon_strategy.py` (Current Algorithm) - **RECENTLY OPTIMIZED**
Implements the primary optimization strategy with major improvements:

**Core Methods:**
- `solve()`: Main optimization loop with safety limits and progress tracking
- `_get_next_polygon()`: Selects next polygon based on travel time from base
- `_calculate_max_plants_per_day()`: Calculates daily planting capacity per polygon
- `_order_plants_if_needed()`: **FIXED** - Manages plant ordering with provider rotation
- `_plant_available_plants()`: **IMPROVED** - Handles planting operations and logistics

**Features:**
- **Provider rotation system**: Cycles through all suppliers systematically
- **Dynamic order sizing**: Based on demand and inventory levels with intelligent priority
- **Progress tracking**: Comprehensive monitoring with infinite loop prevention
- **Flexible planting logic**: Aggressive approach for project completion
- **Enhanced debugging**: Detailed output for tracking inventory, demands, and decisions

#### 4. `utils.py` (Constants and Utilities) - **CORRECTED MAPPINGS**
Contains all system constants and helper functions:

**Constants:**
- `VAN_CAPACITY = 524` (plants per trip)
- `WAREHOUSE_CAPACITY = 10000` (maximum storage)
- `LABOR_TIME = 6.0` (hours per day)
- `PLANTATION_COST_PER_PLANT = 20` (cost per plant)

**FIXED Provider-Species Mapping:**
```python
PROVIDER_SPECIES = {
    "moctezuma": [3, 4, 5, 7, 9, 10] , 
    "venado": [4, 5, 6, 7, 8],
    "laguna_seca": [1, 2, 3, 6, 7]         
}

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
    2: 157,  # 29.96% (largest)
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
python3 main.py
```

4. **View results:**
- Check console output for optimization progress and breakthroughs
- Open `reforestation_calendar.html` in a browser for interactive visualization
- Analyze `detailed_state_log.csv` for daily metrics and improvements

## Algorithm Overview

### Current Strategy: PolygonStrategy

The current implementation uses a polygon-focused approach with breakthrough optimizations:

#### Systematic Provider Rotation**
Cycles through suppliers daily to ensure balanced utilization:
- **Day % 3 == 0**: laguna_seca
- **Day % 3 == 1**: venado  
- **Day % 3 == 2**: moctezuma

This ensures all providers are used and all species can be obtained.

#### **Smart Order Management**
- Orders plants based on next polygon needs and current inventory
- Rotates through providers to access all species
- Intelligent priority based on current demand and inventory gaps
- Respects warehouse capacity and daily order limits
- Provider-species mapping ensures orders are actually possible

#### **Flexible Planting Operations**
- Calculates daily planting capacity based on travel times
- Aggressive planting logic for better completion rates
- Plants available species when inventory and demand align
- Handles mixed species loads and partial van trips
- Handling of proportional species requirements

#### **Comprehensive Progress Tracking**
- Real-time monitoring of inventory, demand, and daily decisions
- Infinite loop prevention with safety limits
- Detailed logging for debugging and optimization
- Progress metrics showing demand reduction over time

### Key Optimizations

#### Warehouse Management**
Maintains optimal species distribution for the warehouse at maximum capacity:
```python
WAREHOUSE_PROPORTIONS = {
    1: 630,   2: 2996,  3: 630,   4: 630,   5: 744,
    6: 573,   7: 1107,  8: 973,   9: 1317,  10: 401
}
```

### Outstanding Performance Results

**Current optimization achieves complete success:**

| Metric | Result |
|--------|--------|
| **Project Completion** | **100% - All demand satisfied** |
| **Total Cost** | **$4,206,338.44** |
| **Project Duration** | **170 days** |
| **Provider Usage** | **All 3 providers utilized** |
| **Species Coverage** | **All 10 species ordered successfully** |
| **Algorithm Status** | **Stable execution - no infinite loops** |
| **Final Inventory** | **Over-ordered 1,459 plants** |

### Enhanced Features

1. **Intelligent Ordering**: Provider rotation ensures access to all species
2. **Progress Monitoring**: Real-time tracking of demand reduction
3. **Debug Output**: Detailed logging of decisions and state changes
4. **Safety Mechanisms**: Infinite loop prevention with controlled execution
5. **Flexible Planting**: Aggressive logic for complete project finish

## Usage Examples

### Basic Optimization Run
```bash
python3 main.py
```

### With Data Collection
```bash
python3 run_with_data_collection.py
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
- **Demand Reduction**: Progress tracking showing improvement over time

### Visualization Features
- **Interactive Calendar**: Daily activities and progress
- **Cost Breakdown**: Detailed expense analysis
- **Progress Tracking**: Demand reduction over time
- **Resource Usage**: Warehouse and labor utilization
- **Provider Analytics**: Usage patterns across all three suppliers

## Current Status & Next Steps

### **Future Enhancements**

#### Priority Areas
1. **Cost Optimization**: Fine-tune provider selection and order timing
2. **Advanced Scheduling**: Optimize planting sequences across polygons
3. **Dynamic Provider Selection**: Real-time cost optimization based on current inventory needs
4. **Constraint Handling**: Better weekend and labor hour management

#### Potential Improvements
- Machine learning-based polygon prioritization
- Advanced inventory management strategies for proportional planting
- Multi-objective optimization (cost vs. time vs. completion rate)
- Predictive ordering based on future planting schedules