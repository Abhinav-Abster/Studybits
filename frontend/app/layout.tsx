import type { Metadata } from "next";
import { Kalam, Patrick_Hand } from "next/font/google";
import "./globals.css";

const kalam = Kalam({
  variable: "--font-kalam",
  subsets: ["latin"],
  weight: ["400", "700"],
});

const patrickHand = Patrick_Hand({
  variable: "--font-patrick-hand",
  subsets: ["latin"],
  weight: "400",
});

export const metadata: Metadata = {
  title: "StudyPlan AI — Your Sketchy Study Buddy",
  description:
    "AI-powered exam prep that turns your syllabus into a personalized study plan with notes, schedules, and quizzes. Built with Google ADK.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${kalam.variable} ${patrickHand.variable} h-full`}
      style={{ colorScheme: "light" }}
      data-theme="light"
    >
      <body
        className="min-h-full flex flex-col"
        style={{
          backgroundColor: "#fdfbf7",
          color: "#2d2d2d",
          fontFamily: `var(--font-patrick-hand), "Patrick Hand", cursive, sans-serif`,
        }}
      >
        {children}
      </body>
    </html>
  );
}
