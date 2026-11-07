import type { Meta, StoryObj } from "@storybook/react";
import { Switch } from "./Switch";
import { sample } from "./sample";

const meta: Meta<typeof Switch> = { title: "Switch", component: Switch, args: sample };
export default meta;
type Story = StoryObj<typeof Switch>;

export const StandardDefault: Story = { args: { variant: "standard", state: "default" } };
export const StandardActive: Story = { args: { variant: "standard", state: "active" } };
export const StandardDisabled: Story = { args: { variant: "standard", state: "disabled" } };
export const StandardLoading: Story = { args: { variant: "standard", state: "loading" } };
export const StandardError: Story = { args: { variant: "standard", state: "error" } };
