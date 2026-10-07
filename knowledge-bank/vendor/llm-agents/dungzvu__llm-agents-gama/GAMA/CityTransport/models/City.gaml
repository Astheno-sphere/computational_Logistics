/**
* Name: CityTransport
* Based on the internal empty template. 
* Author: dung
* Tags: 
*/


model City

//import "Density.gaml"

import "Settings.gaml"

//import "OSMFileImport.gaml"

import "PublicTransport.gaml"

import "Inhabitant.gaml"

import "LLMAgent.gaml"

/* Insert your model definition here */

global {
//	file toulouse_activities_shape_file <- shape_file("../includes/toulouse_activities.shp");
//	geometry shape <- envelope(toulouse_activities_shape_file);

	date _gtfs_calendar_start_date;
	date _gtfs_calendar_end_date;
	
	init {
		create travel_agent_factory number: 1 with: [
			data_trip_list::TRIP_LIST,
			trip_dates_list::TRIP_INFO["calendar"]["dates"],
			trip_calendar_map::TRIP_INFO["calendar"]["data"]
		];
		
//		create activity_loc from: toulouse_activities_shape_file;

//		list<point> locs <- [{2.113423910293682, 43.59364960321025}, {2.2440599995768924, 43.59481024293284}] collect to_GAMA_CRS(each, POPULATION_CRS);
//		write "Locs: " + locs;
//		loop loc over: locs {
//			create activity_loc with: [location::loc];
//		}

		// GTFS calendar
		list<string> _dates_str <- TRIP_INFO["calendar"]["dates"];
		_gtfs_calendar_start_date <- date(_dates_str[0]);
		_gtfs_calendar_end_date <- date(_dates_str[length(_dates_str)-1]);
	}
	
}

species activity_loc {
	aspect default {
		draw circle(100) color: #green;
	}
}

experiment e type: gui {
//	float minimum_cycle_duration <- 0.00001;
	float step <- 120 #s;
//	float step <- 1#mn;
	
	// Map
	parameter "Vehicle Size" category:"GTFS" var: vehicle_display_size <- 20.0 among: [5.0, 10.0, 20.0, 30.0, 40.0];
	parameter "Always show GTFS Routes" category:"GTFS" var: show_always_show_gtfs_routes <- true;
	parameter "Show TRAM routes" category:"GTFS" var: show_type_tram <- false;
	parameter "Show METRO routes" category:"GTFS" var: show_type_metro <- false;
	parameter "Show BUS routes" category:"GTFS" var: show_type_bus <- false;
	parameter "Show TELEO routes" category:"GTFS" var: show_type_teleo <- false;
	parameter "Show Label density" category:"GTFS" var: show_label_density <- 0.5 among: [0.5, 1, 5, 10, 25, 50, 100];
	
	// Inhabitants
	parameter "Inhabitant Size" category:"Inhabitants" var: inhabitant_display_size <- 10.0 among: [5.0, 10.0, 20.0, 50.0, 100.0, 200.0, 400.0];
	parameter "Show Inhabitants" category: "Inhabitants" var: show_inhabitants <- true;
	parameter "Show Inhabitant Label density" category: "Inhabitants" var: show_inhabitants_label_density <- 100 among: [0, 5, 10, 25, 50, 100];
	
	// Verbose
	parameter "Public Transport" category:"Verbose" var: pt_verbose <- false;
	
	// Evaluation
	parameter "Public Transport - Dump stop arrival diff time" category:"Features" var: ft_public_transport_eval <- false;
	parameter "Evaluate - Multimodal Choices" category:"Evaluation" var: ft_evaluate_modality_choices <- true;
	
	reflex save_csv when: ft_public_transport_eval and every(10#mn) {
		float max_early <- max(public_vehicle collect each.metrics_diff_arrival_time_positive);
		float max_late <- min(public_vehicle collect each.metrics_diff_arrival_time_negative);
		float mean_early <- mean(public_vehicle collect each.metrics_diff_arrival_time_positive);
		float mean_late <- mean(public_vehicle collect each.metrics_diff_arrival_time_negative);
		int count_metro <- length(public_vehicle where (each.route_type = TYPE_METRO));
		save [time,max_early,max_late,mean_early,mean_late,count_metro] to: diff_arrival_time_file 
					format:"csv" rewrite: time <= 10#mn;
	}
	
	reflex save_trip_csv when: ft_evaluate_modality_choices and every(1#mn) {
		if time <= 1#mn {
			string person_id <- "";
			int route_type <- 0;
			string moving_id <- "";
			save [machine_time,CURRENT_TIMESTAMP,person_id,route_type,moving_id] to: evaluate_modality_choices_file
					format:"csv" rewrite: true;
		}
		// time, people_name, route_type, moving_id, late_time
		ask inhabitant {
			if self.on_vehicle != nil and self.target_location != nil {
				save [machine_time,CURRENT_TIMESTAMP,person_id,self.on_vehicle.route_type,self.moving_id] to: evaluate_modality_choices_file
					format:"csv" rewrite: false;
			}
		}
	}
	
	reflex save_loc_csv when: every(5#mn) {
		if time <= 5#mn {
			float lon <- 0.0;
			float lat <- 0.0;
			string trip_id <- nil;
			string person_id <- nil;
			save [machine_time,CURRENT_TIMESTAMP,person_id,trip_id,lon,lat] to: evaluate_density_file
					format:"csv" rewrite: true;
		}
		
		ask inhabitant where (!each.is_idle) {
			string trip_id <- self.on_vehicle != nil ? self.on_vehicle.trip_id : nil;
			point ploc <- point(location CRS_transform(POPULATION_CRS));
			save [machine_time,CURRENT_TIMESTAMP,person_id,trip_id, ploc.x, ploc.y]
				to: evaluate_density_file
				format:"csv" rewrite: false;
		}
	}
	
	output {
		display map {
			graphics Strings {
				draw "Date: " + string(current_date)
					at: {10, 10} 
					anchor: #top_left
					border: #black font: font("Geneva", 10, #bold)
					wireframe: true width: 2;
				draw "GTFS Date: " + string(_gtfs_calendar_start_date, "MM/dd") + " - " + string(_gtfs_calendar_end_date, "MM/dd")
					at: {10, 1200} 
					anchor: #top_left
					border: #orange font: font("Geneva", 10, #bold)
					wireframe: true width: 2;
				draw "Active Agents: " + string(length(inhabitant where (each.is_active))) + " / " + string(length(inhabitant))
					at: {10, 2400} 
					anchor: #top_left
					border: #red font: font("Geneva", 10, #bold)
					wireframe: true width: 2;
				draw "Total Activities: " + string(sum(inhabitant collect (each.total_activities)))
					at: {10, 3600} 
					anchor: #top_left
					border: #green font: font("Geneva", 10, #bold)
					wireframe: true width: 2;
			}
			
//			grid density_cell border: #black;
			
			species route;
			species stop;
			species travel_agent_factory;
			species inhabitant;
			species public_vehicle;
			species activity_loc;
		}
	
// Uncomment this to view the arrival time metrics
//		display monitor {
//			chart "Mean arrival time diff" type: series
//			{
//				data "Max Early" value: max(public_vehicle collect each.metrics_diff_arrival_time_positive) color: # green marker_shape: marker_empty style: spline;
//				data "Max Late" value: min(public_vehicle collect each.metrics_diff_arrival_time_negative) color: # red marker_shape: marker_empty style: spline;
//			}
//		}

//		display monitor refresh: every(50 #cycles) {
//			chart "Total bus" type: series
//			{
//				data "Bus" value: length(public_vehicle select (each.route_type = 3)) color: # green marker_shape: marker_empty style: spline;
//			}
//		}
	} 
}