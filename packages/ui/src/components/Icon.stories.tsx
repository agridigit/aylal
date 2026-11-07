import type { Meta, StoryObj } from "@storybook/react";
import { Icon } from "./Icon";
import { sample } from "./sample";

const meta: Meta<typeof Icon> = { title: "Icon", component: Icon, args: sample };
export default meta;
type Story = StoryObj<typeof Icon>;

export const InfoDefault: Story = { args: { variant: "info", state: "default" } };
export const InfoActive: Story = { args: { variant: "info", state: "active" } };
export const InfoDisabled: Story = { args: { variant: "info", state: "disabled" } };
export const InfoLoading: Story = { args: { variant: "info", state: "loading" } };
export const InfoError: Story = { args: { variant: "info", state: "error" } };
export const WarningDefault: Story = { args: { variant: "warning", state: "default" } };
export const WarningActive: Story = { args: { variant: "warning", state: "active" } };
export const WarningDisabled: Story = { args: { variant: "warning", state: "disabled" } };
export const WarningLoading: Story = { args: { variant: "warning", state: "loading" } };
export const WarningError: Story = { args: { variant: "warning", state: "error" } };
export const SuccessDefault: Story = { args: { variant: "success", state: "default" } };
export const SuccessActive: Story = { args: { variant: "success", state: "active" } };
export const SuccessDisabled: Story = { args: { variant: "success", state: "disabled" } };
export const SuccessLoading: Story = { args: { variant: "success", state: "loading" } };
export const SuccessError: Story = { args: { variant: "success", state: "error" } };
