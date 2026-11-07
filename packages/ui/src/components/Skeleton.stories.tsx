import type { Meta, StoryObj } from "@storybook/react";
import { Skeleton } from "./Skeleton";
import { sample } from "./sample";

const meta: Meta<typeof Skeleton> = { title: "Skeleton", component: Skeleton, args: sample };
export default meta;
type Story = StoryObj<typeof Skeleton>;

export const LineDefault: Story = { args: { variant: "line", state: "default" } };
export const LineActive: Story = { args: { variant: "line", state: "active" } };
export const LineDisabled: Story = { args: { variant: "line", state: "disabled" } };
export const LineLoading: Story = { args: { variant: "line", state: "loading" } };
export const LineError: Story = { args: { variant: "line", state: "error" } };
export const BlockDefault: Story = { args: { variant: "block", state: "default" } };
export const BlockActive: Story = { args: { variant: "block", state: "active" } };
export const BlockDisabled: Story = { args: { variant: "block", state: "disabled" } };
export const BlockLoading: Story = { args: { variant: "block", state: "loading" } };
export const BlockError: Story = { args: { variant: "block", state: "error" } };
