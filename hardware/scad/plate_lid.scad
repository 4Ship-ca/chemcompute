// WetStack-0 plate lid: a view window over every well, plus electrode and salt-bridge holes
// over the electrode wells, and optional fiber bosses (Phase 7).
// Measure YOUR plate and edit the first block. Print in PETG; test-fit before adding electrodes.

plate_len = 127.76;  plate_wid = 85.48;  // plate footprint
a1_x      = 17.53;                       // A1 centre from the plate's left edge (column axis)
a1_y      = 13.77;                       // A1 centre from the plate's top edge (row axis)
pitch     = 19.30;                       // well centre spacing
well_d    = 15.6;                        // well inner diameter
clear     = 0.5;  wall = 1.6;  top = 3.0;  skirt = 6;

window_d   = 7.0;   // camera window over every well
electrode_d = 0.9;  // 0.3 mm Pt wire through a 0.9 mm hole, sealed with a dab of epoxy on top
bridge_d   = 3.3;   // 3 mm OD silicone tube
fiber_d    = 1.2;   // 1.0 mm PMMA fiber
port_r     = 5.6;   // radius at which electrode and bridge holes sit

// Electrode wells as [row, column], zero based: A3 A4 A5 A6 B3 (W1..W5)
electrode_wells = [[0,2],[0,3],[0,4],[0,5],[1,2]];
// Wells that get a fiber boss instead of a window (Phase 7), e.g. [[0,2]]
fiber_wells = [];
$fn = 48;

L = plate_len + 2*clear;  W = plate_wid + 2*clear;
function centre(r, c) = [wall + clear + a1_x + c*pitch, wall + clear + (plate_wid - a1_y) - r*pitch];
function has(list, rc) = len([for (x = list) if (x[0] == rc[0] && x[1] == rc[1]) 1]) > 0;

module body() {
  difference() {
    cube([L + 2*wall, W + 2*wall, top + skirt]);
    translate([wall, wall, -1]) cube([L, W, skirt + 1]);
  }
}

difference() {
  union() {
    body();
    for (rc = fiber_wells) translate([each centre(rc[0], rc[1]), skirt]) cylinder(d = 5, h = top + 12);
  }
  for (r = [0:3], c = [0:5]) {
    p = centre(r, c);
    if (!has(fiber_wells, [r, c])) translate([p[0], p[1], -1]) cylinder(d = window_d, h = top + skirt + 2);
    else translate([p[0], p[1], -1]) cylinder(d = fiber_d, h = top + skirt + 20);
    if (has(electrode_wells, [r, c])) {
      translate([p[0] + port_r*cos(135), p[1] + port_r*sin(135), -1]) cylinder(d = electrode_d, h = top + skirt + 2);
      translate([p[0] + port_r*cos(315), p[1] + port_r*sin(315), -1]) cylinder(d = bridge_d, h = top + skirt + 2);
    }
  }
  // row and column labels engraved on the top surface
  for (r = [0:3]) translate([wall + 3, centre(r, 0)[1] - 2, top + skirt - 0.6])
    linear_extrude(1) text(["A","B","C","D"][r], size = 4, font = "Liberation Sans:style=Bold");
  for (c = [0:5]) translate([centre(0, c)[0] - 1.5, W + 2*wall - 6, top + skirt - 0.6])
    linear_extrude(1) text(str(c + 1), size = 4, font = "Liberation Sans:style=Bold");
}
