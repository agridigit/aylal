import type { Meta, StoryObj } from "@storybook/react";
import { Text } from "./Text";
import { sample } from "./sample";

const meta: Meta<typeof Text> = { title: "Text", component: Text, args: sample };
export default meta;
type Story = StoryObj<typeof Text>;

export const BodyDefault: Story = { args: { variant: "body", state: "default" } };
export const BodyActive: Story = { args: { variant: "body", state: "active" } };
export const BodyDisabled: Story = { args: { variant: "body", state: "disabled" } };
export const BodyLoading: Story = { args: { variant: "body", state: "loading" } };
export const BodyError: Story = { args: { variant: "body", state: "error" } };
export const HeadingDefault: Story = { args: { variant: "heading", state: "default" } };
export const HeadingActive: Story = { args: { variant: "heading", state: "active" } };
export const HeadingDisabled: Story = { args: { variant: "heading", state: "disabled" } };
export const HeadingLoading: Story = { args: { variant: "heading", state: "loading" } };
export const HeadingError: Story = { args: { variant: "heading", state: "error" } };
export const CaptionDefault: Story = { args: { variant: "caption", state: "default" } };
export const CaptionActive: Story = { args: { variant: "caption", state: "active" } };
export const CaptionDisabled: Story = { args: { variant: "caption", state: "disabled" } };
export const CaptionLoading: Story = { args: { variant: "caption", state: "loading" } };
export const CaptionError: Story = { args: { variant: "caption", state: "error" } };
