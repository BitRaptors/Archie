import { ScrollProgressBar } from "@/components/ScrollProgressBar"
import { FeedbackBadge } from "@/components/FeedbackBadge"
import { Frame1Hero } from "@/components/frames/Frame1Hero"
import { Frame2Thesis } from "@/components/frames/Frame2Thesis"
import { Frame3UnderTheHood } from "@/components/frames/Frame3UnderTheHood"
import { Frame4Receipts } from "@/components/frames/Frame4Receipts"
import { Frame5Outcomes } from "@/components/frames/Frame5Outcomes"
import { Footer } from "@/components/Footer"

export default function LandingPage() {
  return (
    <main className="relative bg-deep-space-blue text-foreground selection:bg-neon selection:text-black min-h-screen antialiased">
      <ScrollProgressBar />
      <FeedbackBadge />

      <Frame1Hero />
      <Frame2Thesis />
      <Frame3UnderTheHood />
      <Frame4Receipts />
      <Frame5Outcomes />

      <Footer />
    </main>
  )
}
