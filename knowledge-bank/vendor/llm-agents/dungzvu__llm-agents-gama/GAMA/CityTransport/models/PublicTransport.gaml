/**
* Name: PublicTransport
* Based on the internal empty template. 
* Author: dung
* Tags: 
*/


model PublicTransport

import "Settings.gaml"
import "utils/Bitwise.gaml"

global {
	// const
	int TYPE_TRAM <- 0;
	int TYPE_METRO <- 1;
	int TYPE_BUS <- 3;
	int TYPE_TELEO <- 6;
	
	// parameters/display
	bool show_type_tram <- true;
	bool show_type_metro <- true;
	bool show_type_bus <- true;
	bool show_type_teleo <- true;
	bool show_always_show_gtfs_routes <- true;
	float show_label_density <- 1.0;
	
	bool pt_verbose <- false;
	
	// global
	map<string, stop> ALL_STOPS <- map([]);
	map<string, list<public_vehicle>> ROUTE_VEHICLE_MAP <- map([]);
	float vehicle_display_size <- 20.0;
	
	init {
		create route from: routes0_shape_file with: [
			color::rgb(get("color")), 
			route_type::float(get("route_type")),
			shape_id::string(get("shape_id")),
			route_id::string(get("route_id"))
		];
		create stop from: stops0_shape_file with: [
			stop_name::string(get("stop_name")),
			stop_id::string(get("stop_id")),
			route_type::float(get("route_type"))
		];
		
		ask stop {
			ALL_STOPS <+ self.stop_id::self;
		}
	}
}

species travel_agent_factory {
	// parameters
	list<map<string, unknown>> data_trip_list;
	list<string> trip_dates_list;
	map<string,int> trip_calendar_map;
	
	int time_24h -> CURRENT_TIMESTAMP_24H;
	map<string,int> trip_dates_map <- [];
	
	// This value to determine if the time just moved through the next day.
	int day_of_all <- 0;
	int waiting_trip_index <- 0;
	
	init {
		// Build the date calendar index, for faster lookup
		trip_dates_map <- trip_dates_list as_map (each::index_of(trip_dates_list, each));
		
		// Init the first day of trip
		day_of_all <- floor(CURRENT_TIMESTAMP / SECONDS_IN_24H);

		// Find the started value for waiting_trip_index based on the starting_date
		loop i from: 0 to: length(data_trip_list) - 1 {
			map<string, unknown> trip_data <- data_trip_list[i];
			list<list<int>> stop_times <- trip_data["stop_times"];
			int departure_time <- stop_times[0][1];
			if time_24h < departure_time {
				waiting_trip_index <- i;
				break;
			}
		}
		
		write "Init the trip list: - Current Date: " + current_date + " - Trip index starts from: " + waiting_trip_index;
	}
	
	int get_time_now {
		int dof <- floor(CURRENT_TIMESTAMP / SECONDS_IN_24H);
		if dof > day_of_all {
			return time_24h + SECONDS_IN_24H;
		}
		return time_24h;
	}
	
	bool is_trip_available_today(string service_id) {
		string date_str <- string(current_date, "yyyyMMdd");
		if GTFS_FIXED_DATE != nil {
			date_str <- string(GTFS_FIXED_DATE, "yyyyMMdd");
		}
		int date_index <- trip_dates_map[date_str];
		return !even(trip_calendar_map[service_id] div BITWISE_BIT_VAL[date_index]);
	}
	
	reflex schedule_next_trip {
		// TODO: check to reset the index back to 0 when the time is reset as well
		if waiting_trip_index >= length(data_trip_list) {
			int dof <- floor(CURRENT_TIMESTAMP / SECONDS_IN_24H);
			if dof > day_of_all {
				day_of_all <- dof;
				waiting_trip_index <- 0;
			} else {
				// skip this update if the time didn't move to the next day
				return;
			}
		}
		
		int time_now <- get_time_now();
		
		loop i from: waiting_trip_index to: length(data_trip_list) - 1 {
//			if (total > 200) {
//				break;
//			}
			map<string, unknown> trip_data <- data_trip_list[i];
			list<list<int>> stop_times <- trip_data["stop_times"];
			list<int> shape_segments_end_list <- trip_data["shape_segments"];
			
			int departure_time <- stop_times[0][1];
			if (time_now < departure_time) {
				break;
			}
			
//			waiting_trip_index <- (i+1) mod length(data_trip_list);
			waiting_trip_index <- i + 1;

			// check if trip is available
			string service_id <- trip_data["service_id"];
			if !is_trip_available_today(service_id) {
				continue;
			}
			
			// if it's the time, start the trip
			string trip_id <- trip_data["trip_id"];
			string shape_id <- trip_data["shape_id"];
			float route_type <- float(trip_data["route_type"]);
			string route_id <- trip_data["route_id"];
			
			// We still create the vehicle when using these filters.
//			if route_type = TYPE_TRAM and !show_type_tram {
//				return;
//			}
//			if route_type = TYPE_METRO and !show_type_metro {
//				return;
//			}
//			if route_type = TYPE_BUS and !show_type_bus {
//				return;
//			}
//			if route_type = TYPE_TELEO and !show_type_teleo {
//				return;
//			}

			// debug
//			if shape_id != "13585" {
//				continue;
//			}
			
			create public_vehicle with: [
				display_size::vehicle_display_size,
				trip_id::trip_id,
				route_id::route_id,
				shape_id::shape_id,
				route_type::route_type,
				stop_times::stop_times,
				loop_starting_day::day_of_all,
				shape_segments_end_list::shape_segments_end_list
			] {
				if !(route_id in ROUTE_VEHICLE_MAP.keys) {
					ROUTE_VEHICLE_MAP[route_id] <- [];
				}
				ROUTE_VEHICLE_MAP[route_id] << self;
			}
		}
	}
	
}

species route {
	// attributes
	rgb color;
	float route_type;
	string long_name;
	string shape_id;
	string route_id;
	
	
	// others
	list<float> traveled_dist_list;
	float width -> float(ROUTE_DISPLAY_WIDTH[route_type]);
	
	init {
		float accum_dist <- 0.0;
		traveled_dist_list << 0;
		loop i from: 0 to: length(shape.points) - 2 {
			accum_dist <- accum_dist + shape.points[i] distance_to shape.points[i+1];
			traveled_dist_list << accum_dist;
		}
	}
	
	
	aspect default {
		if !show_always_show_gtfs_routes {
			if route_type = TYPE_TRAM and !show_type_tram {
				return;
			}
			if route_type = TYPE_METRO and !show_type_metro {
				return;
			}
			if route_type = TYPE_BUS and !show_type_bus {
				return;
			}
			if route_type = TYPE_TELEO and !show_type_teleo {
				return;
			}
		}
		
		draw (shape + width) color: color;
	}
}

species stop {
	// attributes
	string stop_name;
	string stop_id;
	float route_type;
	float width -> float(ROUTE_DISPLAY_WIDTH[route_type]);
	
	bool show_name <- flip(show_label_density/100.0);
	
	aspect default {
		if route_type = TYPE_TRAM and !show_type_tram {
			return;
		}
		if route_type = TYPE_METRO and !show_type_metro {
			return;
		}
		if route_type = TYPE_BUS and !show_type_bus {
			return;
		}
		if route_type = TYPE_TELEO and !show_type_teleo {
			return;
		}
		
		draw circle(24) + width color: #black;
		draw circle(22) + width color: #white;
		if show_name {
			draw stop_name at: location + {-3,1.5} color: rgb("#888888") font: font('Default', 10, #bold) ; 
		}
	}
}

species public_vehicle skills: [moving] {
	// attributes
	string trip_id;
	string shape_id;
	list<list<int>> stop_times;
	list<int> shape_segments_end_list;
	float route_type;
	// check if the time moved to the next day
	int loop_starting_day;
	
	// others
	string route_id;
	list<point> travel_points;
	list<float> traveled_dist_list;
	int time_24h -> CURRENT_TIMESTAMP_24H;
	// the departure stop of each segment.
	int stop_idx <- 0;
	int travel_shape_idx <- 0;
	point moving_target;
	bool is_stopping -> moving_target = nil;
	rgb color <- rnd_color(255);
	float width -> float(ROUTE_DISPLAY_WIDTH[route_type]);
	
	map<string, int> passengers <- [];
	bool is_full -> length(passengers.keys) >= VEHICLE_MAX_CAPACITY[route_type];
	float capacity_utilization -> length(passengers.keys) * 1.0 / VEHICLE_MAX_CAPACITY[route_type];
	
	// settings
	float close_dist_ <- 5#m;
	float min_dist_to_move -> 5#m * step; // ~ 200 kmh
	
	// display
	float display_size <- 20.0;
	
	// evaluate
	list<float> total_diff_arrival_ <- [0.0, 0.0];
	list<float> metrics_total_passed_stops_ <- [0.0, 0.0];
	float metrics_diff_arrival_time_positive -> (metrics_total_passed_stops_[0] = 0)? 0.0: total_diff_arrival_[0]/metrics_total_passed_stops_[0];
	float metrics_diff_arrival_time_negative -> (metrics_total_passed_stops_[1] = 0)? 0.0: total_diff_arrival_[1]/metrics_total_passed_stops_[1];
	
	init {
		if pt_verbose { write "Start new trip, trip_id: " + trip_id + ", shape_id: " + shape_id;}
		route r <- route first_with (each.shape_id = shape_id);
		route_id <- r.route_id;
		color <- r.color;
		travel_points <- r.shape.points;
		traveled_dist_list <- r.traveled_dist_list;
		
		// init moving skill
		location <- travel_points[travel_shape_idx];
		do update_speed;
		
//		if ['13585','13588'] contains shape_id {
//			write "********** Bus: " + name + ":" + shape_id;
//		}
	}
	
	int get_time_now {
		int dof <- floor(CURRENT_TIMESTAMP / SECONDS_IN_24H);
		if dof > loop_starting_day {
			return time_24h + SECONDS_IN_24H;
		}
		return time_24h;
	}
	
	action get_in(string pname) {
		passengers[pname] <- 0;
	}
	
	action get_off(string pname) {
		remove pname from: passengers;
	}
	
	action update_speed {
		int _start_time <- stop_times[stop_idx][1];
		int _end_time <- stop_times[stop_idx+1][0];
		
		int _start_at <- stop_idx = 0? 0: shape_segments_end_list[stop_idx-1];
		int _end_at <- shape_segments_end_list[stop_idx];
		float _dist <- traveled_dist_list[_end_at] - traveled_dist_list[_start_at];
		// TOOD: debug why the delta_time is zero here
		int _delta_time <- _end_time - _start_time;
		_delta_time <- _delta_time > 0 ? _delta_time: 1;
		
		speed <- _dist / _delta_time;
		if pt_verbose { write "Vehicle [" + trip_id +":"+ shape_id + "] " + "update speed to " + speed; }
	}
	
	action finish_the_trip {
		if pt_verbose { write "Vehicle [" + trip_id +":"+ shape_id + "] " + "finish the trip"; }
		// TODO: notify passengers to get off
		remove self from: ROUTE_VEHICLE_MAP[route_id];
		do die;
	}
	
	// moving skill
	reflex move when: !is_stopping {
		do goto target: moving_target speed: speed;
		if (location distance_to moving_target < close_dist_) {
			location <- moving_target;
			moving_target <- nil;
		}		
	}
	
	reflex follow_the_route when: is_stopping {
		int this_segment_end_at <- shape_segments_end_list[stop_idx];
		int time_now <- get_time_now();
		
		if travel_shape_idx >= this_segment_end_at {
			// If this is the final stop, finish the trip, thank you travelers :)
			if stop_idx >= length(shape_segments_end_list)-1 {
				do finish_the_trip;
				return;
			}

			// capture the metrics
			int _expected_arrival_time <- stop_times[stop_idx+1][0];
			float diff_ <-  _expected_arrival_time - float(time_now);
			int diff_idx_ <- diff_ > 0 ? 0: 1;
			total_diff_arrival_[diff_idx_] <- total_diff_arrival_[diff_idx_] + diff_;
			metrics_total_passed_stops_[diff_idx_] <- metrics_total_passed_stops_[diff_idx_] + 1;
			
			// Go to the next stop
			stop_idx <- stop_idx + 1;
			// We update speed at every beginning of stop
			do update_speed;
		}
		
		// head to the target, hop by hop
		// check departure time when waiting in the stop
		int _start_time <- stop_times[stop_idx][1];
		if time_now < _start_time {
			if pt_verbose { write "Vehicle [" + trip_id +":"+ shape_id + "] " + "wait for departure, now " + time_now + " wait to " + _start_time;}
			return;
		}
		
		// find the next moving_target
		int finding_from <- travel_shape_idx;
		float min_dist <- min_dist_to_move;
		loop i from: travel_shape_idx + 1 to: this_segment_end_at {
			travel_shape_idx <- i;
			if traveled_dist_list[travel_shape_idx] - traveled_dist_list[finding_from] >= min_dist {
				break;
			}
		}

		point next_target <- travel_points[travel_shape_idx];
		if moving_target != next_target {
			if pt_verbose { write  "Vehicle [" + trip_id +":"+ shape_id + "] " + "move to target " + next_target + "speed " + speed;}
			moving_target <- next_target;
		}
	}
	
	
	aspect default {
		if route_type = TYPE_TRAM and !show_type_tram {
			return;
		}
		if route_type = TYPE_METRO and !show_type_metro {
			return;
		}
		if route_type = TYPE_BUS and !show_type_bus {
			return;
		}
		if route_type = TYPE_TELEO and !show_type_teleo {
			return;
		}
		
//		if (destination != nil) {
//			draw line([location, {location.x + -10*display_size * cos(heading), location.y + -10*display_size * sin(heading)}]) + 1.5*display_size + width color: #gray border: true end_arrow: 1.2;
//		}
		if route_type = TYPE_TRAM or route_type = TYPE_METRO {
//			draw circle(5*display_size) + width color: #black;
//			draw circle(2*display_size) + width color: color;
			draw circle(3*display_size) + width color: color border: true;
		} else if route_type = TYPE_BUS {
//			draw square(8*display_size) + width color: #black;
//			draw square(4*display_size) + width color: color;
			draw square(5*display_size) + width color: color border: true;
		} else {
//			draw triangle(12*display_size) + width color: #black;
//			draw triangle(8*display_size) + width color: color;
			draw triangle(8*display_size) + width color: color border: true;
		}
		
	}
	
}
