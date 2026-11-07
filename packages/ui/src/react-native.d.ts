// Typage minimal : react-native est aliasé vers react-native-web (Storybook) ou RN (mobile).
declare module "react-native" {
  export const View: any;
  export const Text: any;
  export const Pressable: any;
  export const TextInput: any;
  export const Switch: any;
  export const StyleSheet: any;
}
