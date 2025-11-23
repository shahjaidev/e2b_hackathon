import { ArrowRight } from 'lucide-react'
import Image from 'next/image'
import Link from 'next/link'

import { Button } from '@/components/ui/button'

const Page = () => {
    return (
        <div className="min-h-screen w-screen flex flex-col">
            <section className="bg-primary text-primary-foreground py-24 text-center px-4">
                <h1 className="text-4xl md:text-6xl font-bold mb-6">
                    Desk Research Agent
                </h1>
                <p className="text-lg md:text-xl mb-8 max-w-2xl mx-auto">
                    Professional research and analysis platform for consulting firms.
                    Accelerate your desk research with AI-powered data analysis and web research.
                </p>
                <Button
                    asChild
                    size="lg"
                    variant="secondary"
                    className="rounded-full"
                >
                    <Link href="/demo">
                        Get Started <ArrowRight className="ml-2 h-5 w-5" />
                    </Link>
                </Button>
            </section>

            <section className="py-16 px-4">
                <div className="max-w-screen-lg mx-auto">
                    <div className="flex justify-center items-center mb-16">
                        <div className="text-center">
                            <p className="text-sm text-muted-foreground mb-4">
                                Trusted by leading consulting firms
                            </p>
                            <div className="flex items-center justify-center gap-8 flex-wrap">
                                <div className="text-2xl font-semibold text-muted-foreground">
                                    EY
                                </div>
                                <div className="text-2xl font-semibold text-muted-foreground">
                                    McKinsey
                                </div>
                                <div className="text-2xl font-semibold text-muted-foreground">
                                    Deloitte
                                </div>
                                <div className="text-2xl font-semibold text-muted-foreground">
                                    BCG
                                </div>
                            </div>
                        </div>
                    </div>

                    <h2 className="text-3xl font-bold text-center mb-8">
                        Professional Research Capabilities
                    </h2>

                    <div className="space-y-6 text-lg max-w-3xl mx-auto">
                        <div className="grid md:grid-cols-2 gap-6">
                            <div className="p-6 border rounded-lg">
                                <h3 className="text-xl font-semibold mb-2">
                                    📊 Data Analysis
                                </h3>
                                <p>
                                    Upload client data files and generate comprehensive insights.
                                    Create professional visualizations and statistical analysis
                                    for your research reports.
                                </p>
                            </div>
                            <div className="p-6 border rounded-lg">
                                <h3 className="text-xl font-semibold mb-2">
                                    🔍 Web Research
                                </h3>
                                <p>
                                    Conduct thorough desk research with AI-powered web search.
                                    Gather market intelligence, industry trends, and competitive
                                    analysis efficiently.
                                </p>
                            </div>
                            <div className="p-6 border rounded-lg">
                                <h3 className="text-xl font-semibold mb-2">
                                    💼 Consulting-Ready
                                </h3>
                                <p>
                                    Generate analysis code and documentation suitable for
                                    client presentations. Export insights and visualizations
                                    for your deliverables.
                                </p>
                            </div>
                            <div className="p-6 border rounded-lg">
                                <h3 className="text-xl font-semibold mb-2">
                                    📈 Professional Reports
                                </h3>
                                <p>
                                    Create publication-quality charts and graphs automatically.
                                    Visualize data with professional styling for executive
                                    presentations.
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            <footer className="mt-auto bg-gray-950 text-gray-400 py-6 px-4">
                <div className="max-w-screen-lg mx-auto flex flex-col md:flex-row justify-between items-center gap-4">
                    <p>© 2025 Desk Research Agent. All rights reserved.</p>
                    <div className="flex items-center gap-2 text-sm">
                        <span>Powered by</span>
                        <Link href="https://e2b.dev" className="hover:underline">
                            <Image
                                src="/e2b-logo.svg"
                                alt="E2B"
                                width={50}
                                height={40}
                                className="inline-block"
                            />
                        </Link>
                    </div>
                </div>
            </footer>
        </div>
    )
}

export default Page
