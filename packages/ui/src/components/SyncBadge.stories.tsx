import type { Meta, StoryObj } from "@storybook/react";
import { SyncBadge } from "./SyncBadge";
import { sample } from "./sample";

const meta: Meta<typeof SyncBadge> = { title: "Sync Badge", component: SyncBadge, args: sample };
export default meta;
type Story = StoryObj<typeof SyncBadge>;

export const BadgeDefault: Story = { args: { variant: "badge", state: "default" } };
export const BadgeActive: Story = { args: { variant: "badge", state: "active" } };
export const BadgeDisabled: Story = { args: { variant: "badge", state: "disabled" } };
export const BadgeLoading: Story = { args: { variant: "badge", state: "loading" } };
export const BadgeError: Story = { args: { variant: "badge", state: "error" } };
export const DotDefault: Story = { args: { variant: "dot", state: "default" } };
export const DotActive: Story = { args: { variant: "dot", state: "active" } };
export const DotDisabled: Story = { args: { variant: "dot", state: "disabled" } };
export const DotLoading: Story = { args: { variant: "dot", state: "loading" } };
export const DotError: Story = { args: { variant: "dot", state: "error" } };
