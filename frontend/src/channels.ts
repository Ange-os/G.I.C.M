/** Identidad visual y labels de canal (Inbox). */

export type ChannelId = "whatsapp" | "instagram" | "web";

export interface ChannelOption {
  id: ChannelId | "all";
  label: string;
}

export const CHANNEL_FILTERS: ChannelOption[] = [
  { id: "all", label: "Todos" },
  { id: "whatsapp", label: "WhatsApp" },
  { id: "instagram", label: "Instagram" },
  { id: "web", label: "Web" },
];

export const CHANNEL_LABELS: Record<ChannelId, string> = {
  whatsapp: "WhatsApp",
  instagram: "Instagram",
  web: "Web",
};

/** Clase CSS para la acuarela del canal en inbox__list-button. */
export function channelWashClass(channel: string): string {
  if (channel === "whatsapp" || channel === "instagram" || channel === "web") {
    return `channel-wash--${channel}`;
  }
  return "channel-wash--default";
}

export function channelLabel(channel: string): string {
  if (channel in CHANNEL_LABELS) {
    return CHANNEL_LABELS[channel as ChannelId];
  }
  return channel;
}
