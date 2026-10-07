import * as React from 'react';
import { CodeHighlighter } from '@ant-design/x';
import { XMarkdown, type ComponentProps } from '@ant-design/x-markdown';
import '@ant-design/x-markdown/themes/light.css';
import '@ant-design/x-markdown/themes/dark.css';
import { useVscodeTheme } from '../theme';

const Code: React.FC<ComponentProps> = (props) => {
  const { className, children } = props;
  const lang = className?.match(/language-(\w+)/)?.[1] || '';

  if (typeof children !== 'string') return null;
  return <CodeHighlighter lang={lang}>{children}</CodeHighlighter>;
};

interface MarkdownRendererProps {
  content: string;
  className?: string;
  style?: React.CSSProperties;
  isDark?: boolean;
  customComponents?: Record<string, React.ComponentType<any>>;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({
  content,
  className,
  style,
  isDark,
  customComponents,
}) => {
  const { isDark: themeIsDark } = useVscodeTheme();
  const darkMode = isDark ?? themeIsDark;

  return (
    <XMarkdown
      components={{
        code: Code,
        ...customComponents,
      }}
      paragraphTag="div"
      className={[darkMode ? 'dark' : 'light', className].filter(Boolean).join(' ')}
      style={{
        fontSize: '13px',
        lineHeight: '1.6',
        color: 'var(--vscode-editor-foreground)',
        ...style,
      }}
    >
      {content}
    </XMarkdown>
  );
};
