// WetStack-0 plate locator frame: holds a 24-well plate in the same spot on the light pad
// every session, with a pocket for the coin vibration motor (the mixer).
// Measure YOUR plate with calipers and edit the first block. Print in PETG, 0.2 mm layers.

plate_len = 127.76;   // outer length of the plate footprint (mm)
plate_wid = 85.48;    // outer width
clear     = 0.6;      // clearance per side
border    = 10;       // frame border width
height    = 5;        // frame height
base      = 1.2;      // floor lip thickness under the plate edge
lip       = 4;        // how far the lip reaches under the plate
motor_d   = 10.4;     // coin motor 1027: 10 mm diameter
motor_h   = 3.2;
$fn = 64;

L = plate_len + 2*clear;
W = plate_wid + 2*clear;

difference() {
  translate([-border, -border, 0]) cube([L + 2*border, W + 2*border, height]);
  translate([0, 0, base]) cube([L, W, height]);                       // plate pocket
  translate([lip, lip, -1]) cube([L - 2*lip, W - 2*lip, height + 2]); // light window
  translate([L + border/2, W/2, height - motor_h]) cylinder(d = motor_d, h = motor_h + 1); // motor pocket
  translate([L - 1, W/2 - 1.5, height - motor_h]) cube([border/2 + 1, 3, motor_h + 1]);   // motor touches plate wall
  translate([L + border/2 - 1, W/2, height - 1.2]) cube([border, 2.2, 2]);                // wire channel
  for (x = [L*0.3, L*0.7]) translate([x, -border - 1, height - 2]) cube([14, border + 2, 3]); // finger notches
}
