import pandas as pd
from datetime import datetime
from optimization_framework import SupplyChainState
from polygon_strategy import PolygonStrategy

def main():
    print("🌳 Loading reforestation optimization data...")
    
    # Load demand data
    demand_df = pd.read_csv('data/encoded_demand.csv', index_col=0)
    demand_df.columns = demand_df.columns.astype(int)  # Convert column names to integers
    print(f"Loaded demand data: {demand_df.shape[0]} polygons, {demand_df.shape[1]} species")
    print(f"Total demand: {demand_df.sum().sum():,} plants")
    
    # Load time matrix
    time_matrix = pd.read_csv('data/tiempos.csv', index_col=0)
    time_matrix.columns = time_matrix.columns.astype(int)  # Convert column names to integers
    print(f"Loaded time matrix: {time_matrix.shape[0]}x{time_matrix.shape[1]} polygons")
    
    # Initialize supply chain state
    start_date = datetime(2025, 9, 1)
    state = SupplyChainState(start_date, demand_df, time_matrix)
    print(f"Initialized supply chain state")
    
    # Create and run optimization strategy
    strategy = PolygonStrategy(state, time_matrix)
    strategy.solve()
    
    print("\n🎉 Optimization completed successfully!")
    
    print(f"\n📊 FINAL RESULTS:")
    print(f"Total cost: ${state.total_cost:,.2f}")
    print(f"Total days: {state.current_day}")
    print(f"Remaining demand: {state.remaining_demand.sum().sum():,} plants")
    print(f"Final warehouse inventory: {state.get_total_warehouse_inventory():,} plants")
    completion_pct = (1 - state.remaining_demand.sum().sum() / demand_df.sum().sum()) * 100
    print(f"Project completion: {completion_pct:.1f}%")

if __name__ == "__main__":
    main() 