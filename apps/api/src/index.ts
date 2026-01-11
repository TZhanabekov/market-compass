import Fastify from "fastify";
import cors from "@fastify/cors";
import { HomeResponseSchema, type HomeResponse } from "@market-compass/shared";

const server = Fastify({ logger: true });

await server.register(cors, {
  origin: true,
  credentials: true,
});

server.get("/health", async () => ({ ok: true }));

// Пример: UI bootstrap endpoint под твою главную страницу
server.get("/v1/ui/home", async (req, reply) => {
  const q = req.query as Partial<{
    model: string;
    sku: string;
    home: string;
    minTrust: string;
  }>;

  const modelKey = q.model ?? "iphone-16-pro";
  const skuKey = q.sku ?? "iphone-16-pro-256gb-black-new";
  const home = (q.home ?? "DE").toUpperCase();
  const minTrust = Math.max(0, Math.min(100, Number(q.minTrust ?? "80")));

  // TODO: заменить на реальные данные из БД/Redis
  const payload: HomeResponse = {
    modelKey,
    skuKey,
    minTrust,
    homeMarket: {
      countryCode: home.slice(0, 2),
      country: "Germany",
      currency: "EUR",
      localPriceUsd: 1299,
      simType: "eSIM + nanoSIM",
      warranty: "EU consumer warranty (varies by retailer)",
    },
    globalWinnerOfferId: "offer_demo_1",
    leaderboard: {
      deals: [
        {
          offerId: "offer_demo_1",
          rank: 1,
          countryCode: "JP",
          country: "Japan",
          city: "Tokyo",
          flag: "🇯🇵",
          shop: "Demo Store",
          availability: "In stock",
          priceUsd: 999,
          taxRefundValue: 80,
          finalEffectivePrice: 919,
          localPrice: "¥149,800",
          trustScore: 92,
          simType: "eSIM + nanoSIM",
          warranty: "Retailer warranty (check details)",
          restrictionAlert: "Check region model compatibility before buying.",
          guideSteps: [
            { icon: "passport", title: "Bring your passport", desc: "Tax-free eligibility may require passport verification." },
            { icon: "receipt", title: "Keep the receipt", desc: "You may need receipts for validation/refund." },
            { icon: "plane", title: "Validate before departure", desc: "Follow the airport procedure to confirm export." }
          ]
        }
      ],
      matchCount: 1,
      lastUpdatedAt: new Date().toISOString(),
    },
  };

  const parsed = HomeResponseSchema.safeParse(payload);
  if (!parsed.success) {
    server.log.error(parsed.error);
    return reply.code(500).send({ error: "Invalid payload" });
  }

  return reply.send(payload);
});

// Redirect endpoint под CTA "Claim Arbitrage"
server.get("/r/offers/:offerId", async (req, reply) => {
  const { offerId } = req.params as { offerId: string };

  // TODO:
  // 1) проверить в БД: есть ли merchant_url
  // 2) если нет — (лениво) вызвать google_immersive_product один раз, закешировать merchant_url
  // 3) сделать 302 redirect на merchant_url; иначе fallback на google shopping link

  // временный безопасный fallback
  const fallback = `https://www.google.com/search?q=${encodeURIComponent(offerId)}`;
  return reply.redirect(302, fallback);
});

const port = Number(process.env.PORT ?? "8080");
const host = process.env.HOST ?? "0.0.0.0";

server.listen({ port, host }).catch((err) => {
  server.log.error(err);
  process.exit(1);
});
