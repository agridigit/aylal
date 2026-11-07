import type { Meta, StoryObj } from "@storybook/react";
import { Card } from "./Card";
import { sample } from "./sample";

const meta: Meta<typeof Card> = { title: "Card", component: Card, args: sample };
export default meta;
type Story = StoryObj<typeof Card>;

export const ElevatedDefault: Story = { args: { variant: "elevated", state: "default" } };
export const ElevatedActive: Story = { args: { variant: "elevated", state: "active" } };
export const ElevatedDisabled: Story = { args: { variant: "elevated", state: "disabled" } };
export const ElevatedLoading: Story = { args: { variant: "elevated", state: "loading" } };
export const ElevatedError: Story = { args: { variant: "elevated", state: "error" } };
export const OutlinedDefault: Story = { args: { variant: "outlined", state: "default" } };
export const OutlinedActive: Story = { args: { variant: "outlined", state: "active" } };
export const OutlinedDisabled: Story = { args: { variant: "outlined", state: "disabled" } };
export const OutlinedLoading: Story = { args: { variant: "outlined", state: "loading" } };
export const OutlinedError: Story = { args: { variant: "outlined", state: "error" } };
