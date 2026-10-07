/**
* Name: Bitwise
* Based on the internal empty template. 
* Author: dung
* Tags: 
*/


model Bitwise

global {
	map<int,int> BITWISE_BIT_VAL <- [];
	
	init {
		// build cache steps
		int val <- 1;
		loop i from: 0 to: 63 {
		    BITWISE_BIT_VAL[i] <- val;
		    val <- val * 2;
		}
	}
}

