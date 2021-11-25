# Arc Welder plugin

This plugin wraps [ArcWelderLib](https://github.com/FormerLurker/ArcWelderLib) by [FormerLurker](https://github.com/FormerLurker) to convert multiple subsequent G0/G1 moves to G2/G3 arcs. This reduces the number of gcode commands necessary to make curved movements, thus potentially removing stutter caused by buffer underruns caused by the 3d printer controller.

Inspired by on a postprocessing script by [yysh12](https://github.com/yysh12)

For further information about ArcWelder antistutter, see https://plugins.octoprint.org/plugins/arc_welder

## Arcwelder Settings

The plugin adds a number of settings to the "Special Modes" category in Cura.

### Arc Welder
This is a global switch to turn the processing of gcode on or off. By default this setting is turned off.

### G90 Influences Extruder
For some printers, sending a G90 or G91 command also changes the E axis mode.  This is required for any printer running Marlin 2+ or a fork of Marlin 2, for Smoothieware, and for Prusa Buddy Firmware (Prusa Mini).  Do NOT add this flag if you are running any other firmware.  If your firmware is not on this list but requires this parameter, please create an issue, and I will update the documentation.

### Resolution (Maximum Path Deviation)
ArcWelder is able to compress line segments into gcode by taking advantage of the fact that a bunch of tiny line segments can, when viewed from a distance, approximate a curve.  However, a true curved path will never match up exactly with a bunch of straight lines, so ArcWelder needs a bit of play in order to create arc commands.  The *resolution argument* tells ArcWelder how much leeway it has with the original toolpath to make an arc.  Increasing this value will result in more compression, and reducing it will improve accuracy.  It is a trade-off, but one that most slicers implement anyway in order to prevent too many tiny movements from overwhelming your firmware.  In fact, ArcWelder can produce toolpaths that are more accurate than simply merging short segments together, making it less 'lossy' than slicer resolution settings.

The default resolution is 0.05mm, which means your toolpaths can deviate by plus or minus 0.025mm.  In general, this produces excellent results and toolpaths that are indistinguishable from the originals with the naked eye.  For extremely high precision parts, you may decrease this value, but this will reduce the amount of compression that can be achieved.

Values above 0.1 are not recommended, as you may encounter overlapping toolpaths.  When using values above 0.1, I recommend you use a visualizer that supports arcs before running your print.

### Path Tolerance Percent (length)
This parameter allows you control how much the length of the final arc can deviate from the original toolpath.  The default value of 5% is absolutely fine in most cases, even though that sounds like a lot.  The key thing to remember here is that your firmware will break the G2/G3 commands into many small segments, essentially reversing the process, so the path length in your firmware will match the original path much more closely.

Originally, this setting was added as a safety feature to prevent prevent bad arcs from being generated in some edge cases.  However, since then a new error detection algorithm was added that makes this unnecessary.  In some cases, especially if your resolution parameter is large (above 0.1), this setting can be used to fine tune the generated arcs, so I left this setting in as is.  99+% of the time, no adjustments will be necessary here.

### Maximum Arc Radius
Allows you to control the maximum radius arc that will be generated with ArcWelder.  This was added as a safety feature to prevent giant arcs from being generated for essentially straight lines.  ArcWelder does have built-in detection to prevent colinear lines from being turned into arcs, but slight deviations due to the precision of the gcodes (usually fixed to 3 decimal places) can cause arcs to be generated where straight lines would do.  Typically no adjustments are necessary from the defaults, but you can adjust this value if you want.

### Allow 3D Arcs
This option allows G2/G3 commands to be generated when using vase mode.  This is an experimental option, and it's possible that there are some unknown firmware issues when adding Z coordinates to arc commands.  That being said, I've gotten pretty good results from this option.  At some point, this will be enabled by default.

### Allow Travel Arcs
This option allows G2/G3 commands to be generated when for travel moves.  In general, most travel moves will not be converted for the average 3D print.  However, for plotters or CNC, or certain slicers that perform wipe actions while retracting, this feature can be useful.  This is an experimental option.

### Allow Dynamic Precision
Not all gcode has the same precision for X, Y, and Z parameters.  Enabling this option will cause the precision to grow as ArcWelder encounters gcodes with higher precision.  This may increase gcode size somewhat, depending on the precision of the gcode commands in your file.

**Important Note**: This option used to be the default, but in some cases I've seen files with unusually high precision.  If it gets too high, the resulting gcode may overrun the gcode buffer size, causing prints to fail.  For that reason, this option has been disabled by default.  I've only seen a few cases where this happens, and it's always been due to custom start/end gcode with extremely high precision.

### Firmware Compensation
**Important**: Do **NOT** enable firmware compensation unless you are sure you need it!  Print quality and compression will suffer if it is enabled needlessly.

Some firmware does not handle arcs with a small radius (under approximately 5mm depending on your settings), which will appear flat instead of curved.  If larger arcs appear flat, it's likely that G2/G3 is disabled.  See [this closed issue for more details](https://github.com/FormerLurker/ArcWelderLib/issues/18), including some illustrations showing what firmware compensation does to your gcode.

This applies to Marlin 1.x (but NOT Marlin 2), Klipper (can be fixed by changing settings), and a few others.  If you notice small radius arcs that print with a flat edge, you may need to enable firmware compensation.  Note that compression may be reduced (perhaps drastically) when firmware compensation is enabled.

This feature is just a workaround, and the best solution will always be to either upgrade your firmware, which is especially important for people running Marlin 1.x or forks, or to adjust your arc interpolation settings (Marlin 2.x and above, Klipper, and others).  If you absolutely cannot upgrade your firmware, this may be your only options.

When firmware compensation is enabled, there are two additional settings to configure:

#### Millimeters Per Arc Segment
This is the default length of a segment in your firmware.  This setting MUST match your firmware setting exactly.  99% of the time this setting should be 1.0 for firmware compensation to work.

#### Minimum Arc Segments
This specifies the minimum number of segments that a circle of the same radius must have and is the parameter that determines how much compensation will be applied.  This setting was inspired by the Marlin 2.0 arc interpolation algorithm and attempts to follow it as closely as possible.  The higher the value, the more compensation will be applied, and the less compression you will get.  A minimum of 14 is recommended.  Values above 24 are NOT recommended.  In general, this should be set as low as possible.

If ArcWelder detects that a generated arc would have fewer segments than specified, it will reject the arc and output regular G0/G1 codes instead.  It's possible that a single arc will be broken into several G2/G3 commands as well, depending on the exact situation.  Note that ArcWelder will never increase the number of GCodes used, so it is limited by the resolution of the source gcode file.

### Extrusion Rate Variance
This feature allows ArcWelder to abort an arc if the extrusion rate changes by more than the value set here.  Note that a setting of 0.050 = 5.0%.  This option especially useful for prints using Cura's Arachne engine, but is also useful for regular prints.  Set this value to 0 to disable this feature.

### Maximum Gcode Length
Some firmware has a problem with long gcode commands, and G2/G3 commands are some of the longest.  You can specify a maximum gcode length to prevent long commands from being generated, which will reduce compression by a tiny amount. Set this value to 0 for no limits.