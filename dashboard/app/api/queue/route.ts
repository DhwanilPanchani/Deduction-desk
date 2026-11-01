import { getQueue } from "@/lib/data";

export async function GET(request: Request) {
  const sort = new URL(request.url).searchParams.get("sort") ?? "priority";
  const data = await getQueue(sort);
  const totalAmount = data.reduce((sum, item) => sum + Number(item.claimed_amount), 0);
  const averageConfidence = data.length
    ? data.reduce((sum, item) => sum + Number(item.confidence), 0) / data.length
    : 0;
  return Response.json({
    data,
    summary: { total_items: data.length, total_amount: totalAmount, average_confidence: averageConfidence },
  });
}
