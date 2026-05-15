import React from "react";
import { ExtraProps } from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import {
  vscDarkPlus,
  oneLight,
} from "react-syntax-highlighter/dist/esm/styles/prism";

// See https://github.com/remarkjs/react-markdown?tab=readme-ov-file#use-custom-components-syntax-highlight

function useIsLightTheme(): boolean {
  const subscribe = React.useCallback((onChange: () => void) => {
    if (typeof document === "undefined") return () => {};
    const observer = new MutationObserver(onChange);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });
    return () => observer.disconnect();
  }, []);

  const getSnapshot = React.useCallback(
    () =>
      typeof document !== "undefined" &&
      document.documentElement.classList.contains("light"),
    [],
  );

  return React.useSyncExternalStore(subscribe, getSnapshot, () => false);
}

type CodeProps = React.ClassAttributes<HTMLElement> &
  React.HTMLAttributes<HTMLElement> &
  ExtraProps;

function CodeBlock({ children, className }: CodeProps) {
  const match = /language-(\w+)/.exec(className || ""); // get the language
  const isLight = useIsLightTheme();

  if (!match) {
    const isMultiline = String(children).includes("\n");
    const inlineStyle = isLight
      ? {
          backgroundColor: "#ECECEC",
          padding: "0.2em 0.4em",
          borderRadius: "4px",
          color: "#606060",
          border: "1px solid #d1d5db",
        }
      : {
          backgroundColor: "#2a3038",
          padding: "0.2em 0.4em",
          borderRadius: "4px",
          color: "#e6edf3",
          border: "1px solid #30363d",
        };

    if (!isMultiline) {
      return (
        <code className={className} style={inlineStyle}>
          {children}
        </code>
      );
    }

    const preStyle = isLight
      ? {
          backgroundColor: "#f5f5f5",
          padding: "1em",
          borderRadius: "4px",
          color: "#1f2937",
          border: "1px solid #d1d5db",
          overflow: "auto" as const,
        }
      : {
          backgroundColor: "#2a3038",
          padding: "1em",
          borderRadius: "4px",
          color: "#e6edf3",
          border: "1px solid #30363d",
          overflow: "auto" as const,
        };

    return (
      <pre style={preStyle}>
        <code className={className}>{String(children).replace(/\n$/, "")}</code>
      </pre>
    );
  }

  return (
    <SyntaxHighlighter
      className="rounded-lg"
      style={isLight ? oneLight : vscDarkPlus}
      language={match?.[1]}
      PreTag="div"
    >
      {String(children).replace(/\n$/, "")}
    </SyntaxHighlighter>
  );
}

/**
 * Component to render code blocks in markdown.
 *
 * Named lowercase because react-markdown maps custom components by HTML
 * element name; the actual rendering (and hook usage) lives in CodeBlock.
 */
export function code({ children, className }: CodeProps) {
  return <CodeBlock className={className}>{children}</CodeBlock>;
}
