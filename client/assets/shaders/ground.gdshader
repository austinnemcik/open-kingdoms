shader_type spatial;
// Terrain for the city view: grass with large-scale colour variation, worn
// dirt around buildings, cobbled roads from a runtime mask (CityRoads), sandy
// river banks, rock on steep slopes and snow on the peaks.
// Vertex colours are masks baked by tools/blender/build_scenery.py:
// R rock, G grass variation, B sand.
// Only uses features available in the Compatibility renderer.

uniform sampler2D grass_tex : source_color, repeat_enable, filter_linear_mipmap_anisotropic;
uniform sampler2D dirt_tex : source_color, repeat_enable, filter_linear_mipmap_anisotropic;
uniform sampler2D cobble_tex : source_color, repeat_enable, filter_linear_mipmap_anisotropic;
uniform sampler2D rock_tex : source_color, repeat_enable, filter_linear_mipmap_anisotropic;
uniform sampler2D noise_tex : repeat_enable, filter_linear_mipmap;
// R road, G worn ground around buildings, B inside the city wall.
uniform sampler2D road_mask : repeat_disable, filter_linear;
uniform float mask_half_extent = 32.0;

varying vec3 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 p = world_pos.xz;
	float n_macro = texture(noise_tex, p * 0.011).r;
	float n_mid = texture(noise_tex, p * 0.06 + vec2(0.37, 0.11)).g;
	float n_fine = texture(noise_tex, p * 0.27).b;

	vec3 grass = mix(texture(grass_tex, p * 0.21).rgb, texture(grass_tex, p * 0.043 + vec2(0.5)).rgb, 0.45);
	float lush = smoothstep(0.25, 0.8, n_macro * 0.55 + COLOR.g * 0.45 + (n_mid - 0.5) * 0.25);
	grass *= mix(vec3(0.80, 0.74, 0.45), vec3(0.42, 0.60, 0.46), lush);
	vec3 dirt = texture(dirt_tex, p * 0.23).rgb;
	vec3 cobble = mix(vec3(0.56, 0.52, 0.46), texture(cobble_tex, p * 0.6).rgb * vec3(0.9, 0.87, 0.82), 0.78);
	vec3 rock = mix(texture(rock_tex, p * 0.085).rgb, texture(rock_tex, p * 0.021).rgb, 0.4);

	vec3 mask = texture(road_mask, p / (2.0 * mask_half_extent) + 0.5).rgb;
	mask *= step(max(abs(p.x), abs(p.y)), mask_half_extent - 0.6);
	float wobble = (n_mid - 0.5) * 0.34 + (n_fine - 0.5) * 0.16;
	float worn = smoothstep(0.25, 0.8, mask.g + wobble);
	float shoulder = smoothstep(0.2, 0.5, mask.r + wobble);
	float road = smoothstep(0.44, 0.56, mask.r + wobble * 0.5);

	// trimmed, slightly brighter lawn inside the wall
	vec3 col = grass * mix(1.0, 1.05, mask.b);
	col = mix(col, dirt, max(worn * 0.8, shoulder * 0.9));
	col = mix(col, cobble, road);
	col = mix(col, mix(dirt, vec3(0.80, 0.72, 0.52), 0.55), smoothstep(0.25, 0.75, COLOR.b + wobble));
	col = mix(col, rock, smoothstep(0.3, 0.7, COLOR.r + wobble * 0.6));
	float snow = smoothstep(12.5, 16.0, world_pos.y + (n_mid - 0.5) * 5.0);
	col = mix(col, vec3(0.92, 0.95, 1.0), snow);
	// river bed darkens under water
	col *= mix(1.0, 0.55, smoothstep(-0.2, -0.9, world_pos.y));

	ALBEDO = col;
	ROUGHNESS = 0.95;
	SPECULAR = 0.08;
}
