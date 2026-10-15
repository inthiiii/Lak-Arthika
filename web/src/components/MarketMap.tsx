import { useEffect, useMemo, useRef } from 'react'
import Map, { Marker, NavigationControl, Popup, type MapRef } from 'react-map-gl/maplibre'
import { setWorkerUrl, type LngLatBoundsLike } from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import 'maplibre-gl/dist/maplibre-gl.css'
import type { MarketPricePoint } from '../api/types'
import { formatDate, formatLkr, movementLabel } from '../utils/format'

interface Props {
  points: MarketPricePoint[]
  selectedMarketId: string | null
  onSelect: (marketId: string) => void
}

setWorkerUrl(workerUrl)

export function MarketMap({ points, selectedMarketId, onSelect }: Props) {
  const mapRef = useRef<MapRef>(null)
  const selected = points.find((point) => point.market_id === selectedMarketId)
  const maxPrice = Math.max(...points.map((point) => point.midpoint_price_lkr), 1)

  const bounds = useMemo(() => {
    if (!points.length) return null
    return points.reduce(
      (value, point) => ({
        west: Math.min(value.west, point.longitude), east: Math.max(value.east, point.longitude),
        south: Math.min(value.south, point.latitude), north: Math.max(value.north, point.latitude),
      }),
      { west: points[0].longitude, east: points[0].longitude, south: points[0].latitude, north: points[0].latitude },
    )
  }, [points])

  useEffect(() => {
    if (bounds && points.length > 1) {
      const mapBounds: LngLatBoundsLike = [
        [bounds.west, bounds.south],
        [bounds.east, bounds.north],
      ]
      mapRef.current?.fitBounds(mapBounds, { padding: 65, duration: 700, maxZoom: 8.4 })
    }
  }, [bounds, points.length])

  return (
    <article className="map-card">
      <div className="card-heading">
        <div><span className="section-index">Map / 01</span><h2>Market movement</h2></div>
        <div className="map-legend" aria-label="Map legend">
          <span><i className="legend-dot legend-dot--falling" />Falling</span>
          <span><i className="legend-dot legend-dot--stable" />Stable</span>
          <span><i className="legend-dot legend-dot--rising" />Rising</span>
        </div>
      </div>
      <div className="map-frame">
        {points.length ? (
          <Map
            ref={mapRef}
            initialViewState={{ longitude: 80.72, latitude: 7.72, zoom: 6.6 }}
            mapStyle="https://tiles.openfreemap.org/styles/bright"
            minZoom={5.5}
            maxZoom={12}
            maxBounds={[78.8, 5.0, 82.7, 10.4]}
          >
            <NavigationControl position="top-right" showCompass={false} />
            {points.map((point) => {
              const movement = movementLabel(point.change_percentage)
              const size = 24 + Math.round((point.midpoint_price_lkr / maxPrice) * 16)
              return (
                <Marker key={point.market_id} longitude={point.longitude} latitude={point.latitude} anchor="center">
                  <button
                    className={`market-marker market-marker--${movement.tone} ${selectedMarketId === point.market_id ? 'is-selected' : ''}`}
                    style={{ width: size, height: size }}
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation()
                      onSelect(point.market_id)
                    }}
                    aria-label={`${point.market_name}, ${movement.label}, ${formatLkr(point.midpoint_price_lkr)}`}
                  ><span aria-hidden="true">{movement.arrow}</span></button>
                </Marker>
              )
            })}
            {selected && (
              <Popup
                longitude={selected.longitude}
                latitude={selected.latitude}
                anchor="bottom"
                offset={28}
                closeButton={false}
                closeOnClick={false}
              >
                <strong>{selected.market_name}</strong>
                <span>{selected.district} · {selected.province}</span>
                <b>{formatLkr(selected.midpoint_price_lkr)} / kg</b>
                <small>{formatDate(selected.observation_date)}</small>
              </Popup>
            )}
          </Map>
        ) : (
          <div className="map-empty"><span>⌖</span><strong>No markets match these filters</strong><p>Try another date, region, or movement.</p></div>
        )}
      </div>
    </article>
  )
}
