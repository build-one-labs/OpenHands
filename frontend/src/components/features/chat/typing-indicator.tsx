import { useTranslation } from "react-i18next";
import { LoadingSpinner } from "#/components/shared/loading-spinner";
import { I18nKey } from "#/i18n/declaration";

export function TypingIndicator() {
  const { t } = useTranslation();

  return (
    <div
      data-testid="typing-indicator"
      className="flex items-center gap-2 rounded-full bg-base-secondary border border-tertiary py-1 pl-1 pr-3 shadow-md"
    >
      <LoadingSpinner size="small" />
      <span className="text-xs font-medium text-content leading-none whitespace-nowrap">
        {t(I18nKey.CHAT_INTERFACE$AGENT_WORKING)}
      </span>
    </div>
  );
}
