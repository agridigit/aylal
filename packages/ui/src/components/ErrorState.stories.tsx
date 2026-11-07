import type { Meta, StoryObj } from "@storybook/react";
import { ErrorState } from "./ErrorState";
import { sample } from "./sample";

const meta: Meta<typeof ErrorState> = { title: "Error State", component: ErrorState, args: sample };
export default meta;
type Story = StoryObj<typeof ErrorState>;

export const InlineDefault: Story = { args: { variant: "inline", state: "default" } };
export const InlineActive: Story = { args: { variant: "inline", state: "active" } };
export const InlineDisabled: Story = { args: { variant: "inline", state: "disabled" } };
export const InlineLoading: Story = { args: { variant: "inline", state: "loading" } };
export const InlineError: Story = { args: { variant: "inline", state: "error" } };
export const PageDefault: Story = { args: { variant: "page", state: "default" } };
export const PageActive: Story = { args: { variant: "page", state: "active" } };
export const PageDisabled: Story = { args: { variant: "page", state: "disabled" } };
export const PageLoading: Story = { args: { variant: "page", state: "loading" } };
export const PageError: Story = { args: { variant: "page", state: "error" } };
