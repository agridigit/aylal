import type { Meta, StoryObj } from "@storybook/react";
import { EmptyState } from "./EmptyState";
import { sample } from "./sample";

const meta: Meta<typeof EmptyState> = { title: "Empty State", component: EmptyState, args: sample };
export default meta;
type Story = StoryObj<typeof EmptyState>;

export const IllustratedDefault: Story = { args: { variant: "illustrated", state: "default" } };
export const IllustratedActive: Story = { args: { variant: "illustrated", state: "active" } };
export const IllustratedDisabled: Story = { args: { variant: "illustrated", state: "disabled" } };
export const IllustratedLoading: Story = { args: { variant: "illustrated", state: "loading" } };
export const IllustratedError: Story = { args: { variant: "illustrated", state: "error" } };
export const PlainDefault: Story = { args: { variant: "plain", state: "default" } };
export const PlainActive: Story = { args: { variant: "plain", state: "active" } };
export const PlainDisabled: Story = { args: { variant: "plain", state: "disabled" } };
export const PlainLoading: Story = { args: { variant: "plain", state: "loading" } };
export const PlainError: Story = { args: { variant: "plain", state: "error" } };
