'use client'

import { cn } from '@/lib/utils'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface MarkdownContentProps {
    content: string
    className?: string
}

export function MarkdownContent({ content, className }: MarkdownContentProps) {
    return (
        <ReactMarkdown
            className={cn(
                'prose prose-sm dark:prose-invert max-w-none',
                'prose-headings:font-semibold prose-headings:tracking-tight prose-headings:text-gray-900 dark:prose-headings:text-gray-100',
                'prose-p:leading-normal prose-p:text-gray-900 dark:prose-p:text-gray-100',
                'prose-strong:text-gray-900 dark:prose-strong:text-gray-100',
                'prose-li:text-gray-900 dark:prose-li:text-gray-100',
                'prose-a:text-gray-900 dark:prose-a:text-gray-100',
                'prose-code:rounded prose-code:bg-muted/50 prose-code:p-1 prose-code:text-gray-900 dark:prose-code:text-gray-100',
                'prose-pre:bg-muted/50 prose-pre:rounded-lg prose-pre:text-gray-900 dark:prose-pre:text-gray-100',
                '[&>*]:text-gray-900 dark:[&>*]:text-gray-100',
                className
            )}
            remarkPlugins={[remarkGfm]}
            components={{
                code({ children, ...props }) {
                    return (
                        <code
                            className="bg-muted/50 px-1 py-0.5 rounded text-gray-900 dark:text-gray-100 font-mono"
                            {...props}
                        >
                            {children}
                        </code>
                    )
                },
                p({ children, ...props }) {
                    return (
                        <p className="text-gray-900 dark:text-gray-100" {...props}>
                            {children}
                        </p>
                    )
                },
                li({ children, ...props }) {
                    return (
                        <li className="text-gray-900 dark:text-gray-100" {...props}>
                            {children}
                        </li>
                    )
                },
                h1({ children, ...props }) {
                    return (
                        <h1 className="text-gray-900 dark:text-gray-100" {...props}>
                            {children}
                        </h1>
                    )
                },
                h2({ children, ...props }) {
                    return (
                        <h2 className="text-gray-900 dark:text-gray-100" {...props}>
                            {children}
                        </h2>
                    )
                },
                h3({ children, ...props }) {
                    return (
                        <h3 className="text-gray-900 dark:text-gray-100" {...props}>
                            {children}
                        </h3>
                    )
                },
            }}
        >
            {content}
        </ReactMarkdown>
    )
}
