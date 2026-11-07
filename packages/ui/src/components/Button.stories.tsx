import type { Meta, StoryObj } from "@storybook/react";
import { Button } from "./Button";
import { sample } from "./sample";

const meta: Meta<typeof Button> = { title: "Button", component: Button, args: sample };
export default meta;
type Story = StoryObj<typeof Button>;

export const PrimaryDefault: Story = { args: { variant: "primary", state: "default" } };
export const PrimaryActive: Story = { args: { variant: "primary", state: "active" } };
export const PrimaryDisabled: Story = { args: { variant: "primary", state: "disabled" } };
export const PrimaryLoading: Story = { args: { variant: "primary", state: "loading" } };
export const PrimaryError: Story = { args: { variant: "primary", state: "error" } };
export const SecondaryDefault: Story = { args: { variant: "secondary", state: "default" } };
export const SecondaryActive: Story = { args: { variant: "secondary", state: "active" } };
export const SecondaryDisabled: Story = { args: { variant: "secondary", state: "disabled" } };
export const SecondaryLoading: Story = { args: { variant: "secondary", state: "loading" } };
export const SecondaryError: Story = { args: { variant: "secondary", state: "error" } };
export const DangerDefault: Story = { args: { variant: "danger", state: "default" } };
export const DangerActive: Story = { args: { variant: "danger", state: "active" } };
export const DangerDisabled: Story = { args: { variant: "danger", state: "disabled" } };
export const DangerLoading: Story = { args: { variant: "danger", state: "loading" } };
export const DangerError: Story = { args: { variant: "danger", state: "error" } };
