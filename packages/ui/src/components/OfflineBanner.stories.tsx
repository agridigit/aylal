import type { Meta, StoryObj } from "@storybook/react";
import { OfflineBanner } from "./OfflineBanner";
import { sample } from "./sample";

const meta: Meta<typeof OfflineBanner> = { title: "Offline Banner", component: OfflineBanner, args: sample };
export default meta;
type Story = StoryObj<typeof OfflineBanner>;

export const BannerDefault: Story = { args: { variant: "banner", state: "default" } };
export const BannerActive: Story = { args: { variant: "banner", state: "active" } };
export const BannerDisabled: Story = { args: { variant: "banner", state: "disabled" } };
export const BannerLoading: Story = { args: { variant: "banner", state: "loading" } };
export const BannerError: Story = { args: { variant: "banner", state: "error" } };
export const CompactDefault: Story = { args: { variant: "compact", state: "default" } };
export const CompactActive: Story = { args: { variant: "compact", state: "active" } };
export const CompactDisabled: Story = { args: { variant: "compact", state: "disabled" } };
export const CompactLoading: Story = { args: { variant: "compact", state: "loading" } };
export const CompactError: Story = { args: { variant: "compact", state: "error" } };
