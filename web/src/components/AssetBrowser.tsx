import { FileUp, Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { assetUrl, fetchCatalog, type CatalogAsset } from "../hooks/useScene";

function assetName(asset: CatalogAsset): string {
  const location = asset.path || asset.source || asset.id;
  return asset.name || location.split(/[\\/]/).pop() || asset.id;
}

function assetDetails(asset: CatalogAsset): string {
  const details = [asset.format.toUpperCase()];
  if (asset.license) details.push(asset.license);
  if (asset.byteSize !== undefined) details.push(formatBytes(asset.byteSize));
  if (asset.animations?.length) details.push(`${asset.animations.length} clips`);
  return details.join(" · ");
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KiB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MiB`;
}

export function AssetBrowser({
  onImport,
  onCreateFromAsset,
}: {
  onImport: (file: File) => void;
  onCreateFromAsset: (asset: CatalogAsset) => void;
}) {
  const [query, setQuery] = useState("");
  const [tag, setTag] = useState("");
  const [assets, setAssets] = useState<CatalogAsset[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      fetchCatalog(query, tag ? [tag] : []).then(setAssets).catch(() => setAssets([]));
    }, 180);
    return () => window.clearTimeout(timer);
  }, [query, tag]);

  return (
    <section className="panel-section assets">
      <div className="panel-heading"><div><h2>Assets</h2><p>Catalog and local GLB files</p></div></div>
      <label className="search-field"><Search size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search assets" aria-label="Search assets" /></label>
      <input className="tag-input" value={tag} onChange={(event) => setTag(event.target.value)} placeholder="Filter by tag" aria-label="Filter by tag" />
      <button className="drop-zone" onClick={() => inputRef.current?.click()} onDragOver={(event) => event.preventDefault()} onDrop={(event) => {
        event.preventDefault();
        const file = event.dataTransfer.files[0];
        if (file) onImport(file);
      }}>
        <FileUp /><span>Drop a GLB or choose a file</span>
      </button>
      <input ref={inputRef} hidden type="file" accept=".glb,model/gltf-binary" onChange={(event) => {
        const file = event.target.files?.[0];
        if (file) onImport(file);
      }} />
      <div className="asset-list">
        {assets.map((asset) => (
          <button key={asset.id} onDoubleClick={() => onCreateFromAsset(asset)}>
            <span className="asset-thumb">
              {asset.thumbnail
                ? <img src={assetUrl(asset.thumbnail)} alt={`${assetName(asset)} thumbnail`} width="42" height="42" />
                : <BoxPreview format={asset.format} />}
            </span>
            <span>
              <strong>{assetName(asset)}</strong>
              <small>{assetDetails(asset)}</small>
              {asset.tags && asset.tags.length > 0 && <small>{asset.tags.join(", ")}</small>}
            </span>
          </button>
        ))}
        {assets.length === 0 && <p className="empty-state">No matching catalog assets.</p>}
      </div>
    </section>
  );
}

function BoxPreview({ format }: { format: string }) {
  return <span aria-hidden="true">{format.toUpperCase()}</span>;
}
