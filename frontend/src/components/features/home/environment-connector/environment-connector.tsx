import React from "react";
import { useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import { I18nKey } from "#/i18n/declaration";
import CircuitIcon from "#/icons/u-circuit.svg?react";
import { CardTitle } from "#/ui/card-title";
import { Typography } from "#/ui/typography";
import { Card } from "#/ui/card";
import { BrandButton } from "../../settings/brand-button";
import { useConnectToEnvironment } from "#/hooks/mutation/use-connect-to-environment";
import { useIsCreatingConversation } from "#/hooks/use-is-creating-conversation";

function isValidEnvironmentUrl(url: string): {
  valid: boolean;
  errorKey?: I18nKey;
} {
  if (!url.trim()) {
    return { valid: false, errorKey: I18nKey.HOME$ENVIRONMENT_URL_REQUIRED };
  }
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      return {
        valid: false,
        errorKey: I18nKey.HOME$ENVIRONMENT_URL_INVALID_SCHEME,
      };
    }
    if (!parsed.hostname) {
      return { valid: false, errorKey: I18nKey.HOME$ENVIRONMENT_URL_INVALID };
    }
    return { valid: true };
  } catch {
    return { valid: false, errorKey: I18nKey.HOME$ENVIRONMENT_URL_INVALID };
  }
}

export function EnvironmentConnector() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [environmentUrl, setEnvironmentUrl] = React.useState("");
  const [validationError, setValidationError] = React.useState<string | null>(
    null,
  );

  const {
    mutate: connectToEnvironment,
    isPending,
    isSuccess,
  } = useConnectToEnvironment();
  const isCreatingConversationElsewhere = useIsCreatingConversation();

  const isConnecting =
    isPending || isSuccess || isCreatingConversationElsewhere;

  const handleConnect = () => {
    const validation = isValidEnvironmentUrl(environmentUrl);
    if (!validation.valid) {
      setValidationError(validation.errorKey ? t(validation.errorKey) : null);
      return;
    }
    setValidationError(null);

    connectToEnvironment(
      {
        environmentUrl: environmentUrl.trim(),
      },
      {
        onSuccess: (data) => {
          // Store the environment URL keyed by both the task-prefixed ID
          // (used during polling) and the raw task ID (used for carry-forward)
          const url = environmentUrl.trim();
          sessionStorage.setItem(
            `environment-url:${data.conversation_id}`,
            url,
          );
          navigate(`/conversations/${data.conversation_id}`);
        },
      },
    );
  };

  return (
    <Card>
      <CardTitle icon={<CircuitIcon width={17} height={14} />}>
        {t(I18nKey.HOME$CONNECT_TO_ENVIRONMENT)}
      </CardTitle>
      <Typography.Text>
        {t(I18nKey.HOME$CONNECT_TO_ENVIRONMENT_DESCRIPTION)}
      </Typography.Text>

      <div className="flex flex-col gap-2">
        <label className="text-xs text-[#A3A3A3]">
          {t(I18nKey.HOME$ENVIRONMENT_URL_LABEL)}
        </label>
        <input
          type="url"
          value={environmentUrl}
          onChange={(e) => {
            setEnvironmentUrl(e.target.value);
            setValidationError(null);
          }}
          placeholder="https://your-environment.example.com"
          className="w-full rounded-md border border-[#525252] bg-[#1A1A1A] px-3 py-2 text-sm text-white placeholder:text-[#6B6B6B] focus:border-[#7B61FF] focus:outline-none"
          data-testid="environment-url-input"
        />
        {validationError && (
          <span className="text-xs text-red-400">{validationError}</span>
        )}
      </div>

      <BrandButton
        testId="connect-to-environment-button"
        variant="primary"
        type="button"
        onClick={handleConnect}
        isDisabled={isConnecting || !environmentUrl.trim()}
        className="w-auto absolute bottom-5 left-5 right-5 font-semibold"
      >
        {!isConnecting && t(I18nKey.HOME$CONNECT)}
        {isConnecting && t(I18nKey.HOME$CONNECTING)}
      </BrandButton>
    </Card>
  );
}
