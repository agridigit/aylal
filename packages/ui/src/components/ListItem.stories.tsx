import type { Meta, StoryObj } from "@storybook/react";
import { ListItem } from "./ListItem";
import { sample } from "./sample";

const meta: Meta<typeof ListItem> = { title: "List Item", component: ListItem, args: sample };
export default meta;
type Story = StoryObj<typeof ListItem>;

export const SimpleDefault: Story = { args: { variant: "simple", state: "default" } };
export const SimpleActive: Story = { args: { variant: "simple", state: "active" } };
export const SimpleDisabled: Story = { args: { variant: "simple", state: "disabled" } };
export const SimpleLoading: Story = { args: { variant: "simple", state: "loading" } };
export const SimpleError: Story = { args: { variant: "simple", state: "error" } };
export const WithIconDefault: Story = { args: { variant: "withIcon", state: "default" } };
export const WithIconActive: Story = { args: { variant: "withIcon", state: "active" } };
export const WithIconDisabled: Story = { args: { variant: "withIcon", state: "disabled" } };
export const WithIconLoading: Story = { args: { variant: "withIcon", state: "loading" } };
export const WithIconError: Story = { args: { variant: "withIcon", state: "error" } };
