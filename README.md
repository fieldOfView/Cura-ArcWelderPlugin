# Arc Welder plugin

This plugin wraps [ArcWelderLib](https://github.com/FormerLurker/ArcWelderLib) by [FormerLurker](https://github.com/FormerLurker) to convert multiple subsequent G0/G1 moves to G2/G3 arcs. This reduces the number of gcode commands necessary to make curved movements, thus potentially removing stutter caused by buffer underruns caused by the 3d printer controller.

Inspired by on a postprocessing script by [yysh12](https://github.com/yysh12)

For further informatio about ArcWelder antistutter, see https://plugins.octoprint.org/plugins/arc_welder