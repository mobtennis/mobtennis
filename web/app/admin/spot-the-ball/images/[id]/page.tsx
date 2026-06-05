import { SpotTheBallImageAdmin } from "@/components/SpotTheBallImageAdmin";

export const revalidate = 0;

export const metadata = {
  title: "Spot the ball · image",
  robots: { index: false, follow: false },
};

export default async function ImagePage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ key?: string }>;
}) {
  const { id } = await params;
  const { key } = await searchParams;
  if (!key) {
    return (
      <div className="p-4 text-sm">
        <h1 className="text-lg font-semibold">Admin key required</h1>
      </div>
    );
  }
  if (!/^\d+$/.test(id)) {
    return (
      <div className="p-4 text-sm">
        <h1 className="text-lg font-semibold">Bad image id</h1>
      </div>
    );
  }
  return <SpotTheBallImageAdmin imageId={Number(id)} adminKey={key} />;
}
