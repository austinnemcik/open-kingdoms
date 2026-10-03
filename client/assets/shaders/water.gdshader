shader_type spatial;
// Stylised river and lake water: two scrolling noise layers pick between a
// deep and a shallow colour and add drifting highlights. Opaque on purpose
// (no depth or screen textures) so it works in the Compatibility renderer.

uniform sampler2D noise_tex : repeat_enable, filter_linear_mipmap;
uniform vec3 deep_color : source_color = vec3(0.13, 0.42, 0.60);
uniform vec3 shallow_color : source_color = vec3(0.33, 0.68, 0.76);

varying vec3 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 p = world_pos.xz;
	float a = texture(noise_tex, p * 0.13 + TIME * vec2(0.010, 0.006)).r;
	float b = texture(noise_tex, p * 0.27 - TIME * vec2(0.007, 0.011)).g;
	float ripple = a * 0.55 + b * 0.45;
	vec3 col = mix(deep_color, shallow_color, smoothstep(0.3, 0.8, ripple) * 0.7);
	float glint = texture(noise_tex, p * 0.9 + TIME * vec2(0.02, -0.015)).b;
	col += vec3(0.14) * smoothstep(0.7, 0.76, glint * 0.6 + ripple * 0.4);
	ALBEDO = col;
	ROUGHNESS = 0.2;
	SPECULAR = 0.5;
}
