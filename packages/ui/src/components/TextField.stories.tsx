import type { Meta, StoryObj } from "@storybook/react";
import { TextField } from "./TextField";
import { sample } from "./sample";

const meta: Meta<typeof TextField> = { title: "Text Field", component: TextField, args: sample };
export default meta;
type Story = StoryObj<typeof TextField>;

export const OutlinedDefault: Story = { args: { variant: "outlined", state: "default" } };
export const OutlinedActive: Story = { args: { variant: "outlined", state: "active" } };
export const OutlinedDisabled: Story = { args: { variant: "outlined", state: "disabled" } };
export const OutlinedLoading: Story = { args: { variant: "outlined", state: "loading" } };
export const OutlinedError: Story = { args: { variant: "outlined", state: "error" } };
export const FilledDefault: Story = { args: { variant: "filled", state: "default" } };
export const FilledActive: Story = { args: { variant: "filled", state: "active" } };
export const FilledDisabled: Story = { args: { variant: "filled", state: "disabled" } };
export const FilledLoading: Story = { args: { variant: "filled", state: "loading" } };
export const FilledError: Story = { args: { variant: "filled", state: "error" } };
