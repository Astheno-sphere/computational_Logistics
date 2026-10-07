/**
* Name: People
* Based on the internal empty template. 
* Author: dung
* Tags: 
*/


model People

import "PublicTransport.gaml"

global {
	float inhabitant_display_size <- 20.0;
	// Display touch variables
	bool show_inhabitants <- true;
	int show_inhabitants_label_density <- 100;
	
	map<string, inhabitant> INHABITANT_MAP <- [];
}


/* Insert your model definition here */

species in_transfer skills: [moving] virtual: true {
	point moving_target;
	bool is_stop_moving -> moving_target = nil;
	// metrics, total distance that agent has traveled so far
	float last_dist_traveled <- 0.0;
	
	float speed <- 2#m/#s;
	float moving_close_dist <- 15#m;
	
	reflex moving_update when: !is_stop_moving {
		// TODO: move along the road extracted from OSM data
		do goto target: moving_target speed: speed;
		last_dist_traveled <- last_dist_traveled + real_speed * step;
		if (location distance_to moving_target < moving_close_dist) {
			location <- moving_target;
			moving_target <- nil;
		}		
	}
	
	action metrics_reset_dist_traveled {
		last_dist_traveled <- 0.0;
	}
}

species passenger parent: in_transfer virtual: true {
	// state
	bool is_active <- false;
	
	// fast query
	map<string, list<public_vehicle>> route_vehicle_map;
	
	// parameters
	string moving_id;  // TravelPlan.id
	string activity_id; // Personal Activity ID
	string purpose;
	int expected_arrive_at;
	int schedule_at;
	map<string, unknown> raw_trip;
	string moving_description;
	point target_location -> length(list_destination) > 0 ? list_destination[length(list_destination)-1]: nil;
	
	string _ROUTE_NONE_ <- "__NONE__";
	
	// attributes
	public_vehicle on_vehicle;
	float get_in_vehicle_dist <- 25#m;
	int step_idx <- 0;
	list<point> list_destination <- [];
	list<string> list_destination_stop_name <- [];
	list<string> list_route_id <- [];
	list<list<string>> list_shape_id <- [];
	// for metrics, the time agent switched to the current segment
	int step_started_at <- 0;
	float on_vehicle_capacity_utilization <- 0.0;
	float trip_traveled_duration <- 0.0;
	
	// metrics actions
	action submit_ob_transfer(float segment_duration, float dist, int ob_step_idx) virtual: true;
	action submit_ob_transit(float segment_duration, float dist, int ob_step_idx, float capacity) virtual: true;
	action submit_ob_tripfeedback(float trip_duration) virtual: true;
	action submit_vehicle_wait_time(float wait_duration, int ob_step_idx) virtual: true;
	int total_activities <- 0;
	
	action passenger_reset_plan {
		list_destination <- [];
		list_destination_stop_name <- [];
		list_route_id <- [];
		list_shape_id <- [];
	}

	action passenger_set_plan(map<string, float> plan_target, list<map<string, unknown>> legs, map<string, unknown> raw) {		
		total_activities <- total_activities + 1;
		
		// NOTE: set location immediately when legs is empty
		// TODO: should implement other mobilities than public transport
		if length(legs) = 0 {
			point start_point <- point(to_GAMA_CRS(
				{float(raw["plan"]["start_location"]["lon"]), float(raw["plan"]["start_location"]["lat"])}, 
				POPULATION_CRS
			));
			location <- start_point;
		}
					
		is_active <- true;
		
		raw_trip <- raw;
		
		step_idx <- 0;
		// reset metrics
		trip_traveled_duration <- 0.0;
		step_started_at <- CURRENT_TIMESTAMP;
		
		do passenger_reset_plan();
		
		if length(legs) > 0 {
			// Add walking segment first
			point start_point <- point(to_GAMA_CRS(
				{float(legs[0]["start_location"]["lon"]), float(legs[0]["start_location"]["lat"])}, 
				POPULATION_CRS
			));
			list_destination << start_point;
			list_destination_stop_name << string(legs[0]["start_location"]["stop"]);
			list_route_id << _ROUTE_NONE_;
			list_shape_id << nil;
			
			loop leg over: legs {
				point end_point <- point(to_GAMA_CRS(
					{float(leg["end_location"]["lon"]), float(leg["end_location"]["lat"])}, 
					POPULATION_CRS
				));
				list_destination << end_point;
				list_destination_stop_name << string(leg["end_location"]["stop"]);
				string transit_route <- string(leg["transit_route"]);
				list_route_id << (bool(leg["is_transfer"]) ? _ROUTE_NONE_: string(leg["transit_route"]));
				list_shape_id << (bool(leg["is_transfer"]) ? "": (leg["shape_id"] collect string(each)));
			}
		}
		
		// End with a walking segment
		point end_point <- point(to_GAMA_CRS(
			{float(plan_target["lon"]), float(plan_target["lat"])}, 
			POPULATION_CRS
		));
		list_destination << end_point;
		list_destination_stop_name << purpose;
		list_route_id << _ROUTE_NONE_;
		list_shape_id << nil;
		
//		write "======= Plan";
//		write "Destination: " + list_destination;
//		write "Route_id: " + list_route_id;
	}
	
	action on_finish_plan virtual: true {
		
	}
	
//	reflex follow_the_vehicle when: on_vehicle != nil {
//		if !dead(on_vehicle) {
//			// follow the vehicle if we're sitting on it
//			location <- on_vehicle.location;
//		}
//		else {
//			point dest <- list_destination[step_idx];
//			location <- dest;
//			on_vehicle <- nil;
//		}
//		
////		// get off if we reach to the last stop, or close to the destination
////		point dest <- list_destination[step_idx];
////		if location distance_to dest <= get_in_vehicle_dist or dead(on_vehicle){
////			if !dead(on_vehicle) {
////				ask on_vehicle {
////					do get_off(name);
////				}
////			}
////			on_vehicle <- nil;
////			location <- dest;
////		}
//	}
	
		
	reflex follow_the_vehicle when: on_vehicle != nil {
		if CURRENT_TIMESTAMP < schedule_at {
			return;
		}
		
		if !dead(on_vehicle) {
			// follow the vehicle if we're sitting on it
			location <- on_vehicle.location;
		}
		
		// get off if we reach to the last stop, or close to the destination
		point dest <- list_destination[step_idx];
		if location distance_to dest <= get_in_vehicle_dist or dead(on_vehicle){
			if !dead(on_vehicle) {
				ask on_vehicle {
					do get_off(name);
				}
				// metrics
				on_vehicle_capacity_utilization <- on_vehicle.capacity_utilization;
			}		
			on_vehicle <- nil;
			location <- dest;
		}
		
	}
	
	reflex follow_the_plan_when_stop when: target_location != nil and is_stop_moving and on_vehicle = nil {
		if CURRENT_TIMESTAMP < schedule_at {
			return;
		}
		
		point dest <- list_destination[step_idx];
		// move to the next step if reached to the step destination
		if location distance_to dest < moving_close_dist {
			// try to submit observation
			bool is_transfer <- list_route_id[step_idx] = _ROUTE_NONE_;
			float _duration <- float(CURRENT_TIMESTAMP-step_started_at);
			// metrics
			trip_traveled_duration <- trip_traveled_duration + _duration;
			
			if is_transfer {
				do submit_ob_transfer(
					_duration,
					last_dist_traveled,
					step_idx
				);
			} else {
				do submit_ob_transit(
					_duration,
					last_dist_traveled,
					step_idx,
					on_vehicle_capacity_utilization
				);
			}
			step_idx <- step_idx + 1;
			location <- dest;
			
			// reset metrics
			step_started_at <- CURRENT_TIMESTAMP;
			last_dist_traveled <- 0.0;
		}
		
//		write "Stop: " + step_idx;
		
		if step_idx >= length(list_destination) {
			location <- target_location;
			
			do submit_ob_tripfeedback(trip_traveled_duration);
			
			do passenger_reset_plan();
			do on_finish_plan();
			
			activity_id <- nil;
			return;
		}
		
		// schedule the next move, self-move or waiting for a vehicle
		string route_id <- list_route_id[step_idx];
		list<string> shape_id_list <- list_shape_id[step_idx];
		if route_id != _ROUTE_NONE_ {
			if route_id in route_vehicle_map.keys {
				// TODO: consider the capacity of the vehicle
				public_vehicle closest_vehicle <- (route_vehicle_map[route_id] 
						first_with (shape_id_list contains each.shape_id and !each.is_full and distance_to(each, self) < get_in_vehicle_dist)
				);
				if closest_vehicle != nil {
					on_vehicle <- closest_vehicle;
					ask closest_vehicle {
						do get_in(name);
					}
					
					float waiting_duration <- float(CURRENT_TIMESTAMP-step_started_at);
					do submit_vehicle_wait_time(waiting_duration, step_idx);
					
					// metrics
					on_vehicle_capacity_utilization <- on_vehicle.capacity_utilization;
				}
			}
		} else {
			// self move to the target
			point dest2 <- list_destination[step_idx];
			moving_target <- dest2;
		}
	}
}

species inhabitant parent: passenger {
	// parameters/identity
	string person_name;
	string person_id;
//	int age;
	bool is_llm_based <- false;
	
	// state
	int time_24h -> CURRENT_TIMESTAMP_24H;
	bool is_idle -> target_location = nil;
	
	list<map<string,unknown>> OB_LIST <- [];
	
	// display
	bool show_name <- flip(show_inhabitants_label_density/100.0);
	
	init {
		purpose <- "home";
	}
	
	action on_finish_plan {
		write "Hura, person " + person_id + " finished the plan";
		// TODO: notify the llm-agent
	}
	
	action submit_ob_transfer(float segment_duration, float dist, int ob_step_idx) {
		map<string,unknown> ob <- [
			"type"::"transfer",
			"timestamp"::CURRENT_TIMESTAMP,
			"moving_id"::moving_id,
			"activity_id"::activity_id,
			"distance"::dist,
			"duration"::segment_duration,
			"from_name"::(ob_step_idx = 0? nil: list_destination_stop_name[ob_step_idx-1]),
			"destination_name"::list_destination_stop_name[ob_step_idx]
		];
		OB_LIST << ob;
	}
	
	action submit_ob_transit(float segment_duration, float dist, int ob_step_idx, float capacity) {    
		map<string,unknown> ob <- [
			"type"::"transit",
			"timestamp"::CURRENT_TIMESTAMP,
			"waiting_time"::0,
			"moving_id"::moving_id,
			"activity_id"::activity_id,
			"distance"::dist,
			"duration"::segment_duration,
			"capacity_utilization"::capacity,
			"departure_stop_name"::(ob_step_idx > 0? list_destination_stop_name[ob_step_idx-1]:""),
			"arrival_stop_name"::list_destination_stop_name[ob_step_idx],
			"by_vehicle_route_id"::list_route_id[ob_step_idx]
		];
		OB_LIST << ob;
	}
	
	action submit_vehicle_wait_time(float wait_duration, int ob_step_idx) {
		map<string,unknown> ob <- [
			"type"::"wait_in_stop",
			"timestamp"::CURRENT_TIMESTAMP,
			"activity_id"::activity_id,
			"duration"::wait_duration,
			"stop_name"::list_destination_stop_name[ob_step_idx-1],
			"by_vehicle_route_id"::list_route_id[ob_step_idx]
		];
		OB_LIST << ob;
	}
	
	action submit_ob_tripfeedback(float trip_duration) {
		float plan_duration <- (float(raw_trip["plan"]["end_time"]) - float(raw_trip["plan"]["start_time"])) / 1000.0;
		map<string,unknown> ob <- [
			"type"::"arrival",
			"timestamp"::CURRENT_TIMESTAMP,
			"moving_id"::moving_id,
			"activity_id"::activity_id,
			"duration"::trip_duration,
			"plan_duration"::plan_duration,
			"started_at"::CURRENT_TIMESTAMP-trip_duration,
			"arrive_at"::CURRENT_TIMESTAMP,
			"expected_arrive_at"::expected_arrive_at,
			"prepare_before_seconds"::raw_trip["prepare_before_seconds"],
			"purpose"::purpose
		];
		OB_LIST << ob;
	}
	
	string get_action_emoji {
		if !is_idle {
			if list_route_id != nil and list_route_id[step_idx] = _ROUTE_NONE_ {
				return PURPOSE_ICON_MAP["__WALKING__"];
			}
			return PURPOSE_ICON_MAP["__MOVING__"];
		}
		if purpose in PURPOSE_ICON_MAP.keys {
			return PURPOSE_ICON_MAP[purpose];
		}
		return "";
	}
	
	aspect default {
		if !show_inhabitants {
			return;
		}
		
		draw 
			square((is_llm_based ? 20: 9)*inhabitant_display_size) 
			color: (is_llm_based ? #red : #gray)
			border: true;
		if show_name {
			draw (get_action_emoji()) at: location + {-3,1.5} anchor: #bottom_center color: (is_llm_based ? #red : #blue) font: font('Default', (is_llm_based ? 18 : 16), #bold);
			draw (person_id) at: location + {-3,1.5} anchor: #top_left color: (is_llm_based ? #red : #blue) font: font('Default', (is_llm_based ? 10 : 8), #bold); 
		}
	}
}
