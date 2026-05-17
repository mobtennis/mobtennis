module.exports = function (api) {
  api.cache(true);
  return {
    // NativeWind v4 setup — jsxImportSource hooks our JSX runtime to NativeWind's,
    // which is what wires `className` through to native style props. The
    // separate "nativewind/babel" preset is v2-era and causes a silent white-
    // screen render in v4, so we don't include it.
    presets: [["babel-preset-expo", { jsxImportSource: "nativewind" }]],
    // Reanimated 4 (SDK 55) split worklets into its own package; this plugin
    // must be registered. Must run *last* if other plugins are added.
    plugins: ["react-native-worklets/plugin"],
  };
};
