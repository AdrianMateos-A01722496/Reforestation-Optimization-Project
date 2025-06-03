import pandas as pd
from datetime import datetime
from optimization_framework import SupplyChainState
from polygon_strategy import PolygonStrategy
from daily_data_collector import DailyDataCollector

def main():
    # Load demand data and time matrix
    demand = pd.read_csv('data/encoded_demand.csv', index_col=0)
    demand.columns = demand.columns.astype(int)
    time_matrix = pd.read_csv('data/tiempos.csv', index_col=0)
    
    # Initialize state and strategy
    start_date = datetime(2025, 9, 1)
    state = SupplyChainState(start_date, demand, time_matrix)
    strategy = PolygonStrategy(state, time_matrix)
    
    # Initialize data collector
    data_collector = DailyDataCollector(start_date)
    
    print(f"🌱 Starting reforestation optimization with data collection...")
    print(f"📊 Initial demand: {state.remaining_demand.sum().sum():,} plants")
    print(f"📅 Start date: {start_date.strftime('%Y-%m-%d')}")
    
    # Modified solve method with data collection
    max_days = 1000
    days_without_progress = 0
    max_days_without_progress = 20
    last_demand = state.remaining_demand.sum().sum()
    
    while (not state.remaining_demand.empty and 
           state.remaining_demand.sum().sum() > 0 and
           state.current_day < max_days):
        
        current_demand = state.remaining_demand.sum().sum()
        
        # Check for progress
        if current_demand < last_demand:
            days_without_progress = 0
            last_demand = current_demand
        else:
            days_without_progress += 1
            if days_without_progress >= max_days_without_progress:
                print(f"\n⚠️  No progress for {max_days_without_progress} days - stopping")
                break
        
        # Process the day
        is_weekend = state.is_weekend(state.current_day)
        if is_weekend:
            strategy._order_plants_if_needed()
        else:
            planted_any = strategy._plant_available_plants()
            if not planted_any or state.remaining_labor_hours > 0:
                strategy._order_plants_if_needed()
        
        # Collect daily data AFTER processing the day
        day_data = data_collector.collect_day_data(state, state.current_day)
        
        # Report progress
        if state.current_day % 20 == 0 or current_demand < 5000:
            completion_pct = day_data["completion_percentage"]
            print(f"\n📅 Day {state.current_day} ({day_data['date']}):")
            print(f"   🎯 Progress: {completion_pct:.1f}% complete")
            print(f"   🌱 Remaining: {current_demand:,} plants")
            print(f"   🏭 Warehouse: {day_data['warehouse_inventory_total']:,} plants")
            print(f"   💰 Cost so far: ${day_data['total_cost_so_far']:,.2f}")
            
            if current_demand < 1000:
                print("🔥 FINAL PHASE - Close to completion!")
        
        # Advance to next day
        state.advance_day()
    
    # Collect final day data
    final_day_data = data_collector.collect_day_data(state, state.current_day)
    
    print("\n🎉 Optimization completed!")
    print(f"📊 Final Results:")
    print(f"   📅 Total days: {state.current_day}")
    print(f"   💰 Total cost: ${state.total_cost:,.2f}")
    print(f"   🌱 Final demand: {state.remaining_demand.sum().sum():,} plants")
    print(f"   🏭 Final inventory: {state.get_total_warehouse_inventory():,} plants")
    print(f"   🎯 Completion: {final_day_data['completion_percentage']:.1f}%")
    
    # Save data to JSON
    json_file = data_collector.save_to_json()
    
    # Get milestones
    milestones = data_collector.get_completion_timeline()
    print(f"\n🏆 Major Milestones:")
    for milestone in milestones:
        print(f"   {milestone['type']} - Day {milestone['day']} ({milestone['date']})")
    
    return json_file, data_collector

if __name__ == "__main__":
    json_file, collector = main()
    print(f"\n✅ Daily data saved to: {json_file}")
    print("🎨 Ready to create interactive calendar!") 