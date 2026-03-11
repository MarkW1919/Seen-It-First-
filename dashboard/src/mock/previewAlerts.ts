export interface PreviewAlert {
  id: string;
  ts: string;
  plate: string;
  vehicle: string;
  camera: string;
  confidence: number;
  latitude: number;
  longitude: number;
  photoUrl: string;
  make: string;
  model: string;
  color: string;
  yearRange: string;
}

export const PREVIEW_ALERTS: PreviewAlert[] = [
  {
    id: "alert-001",
    ts: "01:14:22",
    plate: "6BZN220",
    vehicle: "White Toyota Camry",
    camera: "Street Cam 2",
    confidence: 0.93,
    latitude: 37.42172,
    longitude: -122.08408,
    photoUrl: "https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?auto=format&fit=crop&w=900&q=80",
    make: "Toyota",
    model: "Camry",
    color: "White",
    yearRange: "2018-2021",
  },
  {
    id: "alert-002",
    ts: "01:12:08",
    plate: "3LPM771",
    vehicle: "Black Ford Explorer",
    camera: "Gate North",
    confidence: 0.89,
    latitude: 37.42243,
    longitude: -122.08229,
    photoUrl: "https://images.unsplash.com/photo-1552519507-da3b142c6e3d?auto=format&fit=crop&w=900&q=80",
    make: "Ford",
    model: "Explorer",
    color: "Black",
    yearRange: "2019-2022",
  },
  {
    id: "alert-003",
    ts: "01:09:44",
    plate: "9XCA441",
    vehicle: "Gray Honda Accord",
    camera: "Lot East",
    confidence: 0.86,
    latitude: 37.42061,
    longitude: -122.08155,
    photoUrl: "https://images.unsplash.com/photo-1549923746-c502d488b3ea?auto=format&fit=crop&w=900&q=80",
    make: "Honda",
    model: "Accord",
    color: "Gray",
    yearRange: "2017-2020",
  },
  {
    id: "alert-004",
    ts: "01:04:57",
    plate: "1JFD552",
    vehicle: "Blue Chevy Tahoe",
    camera: "Street Cam 1",
    confidence: 0.82,
    latitude: 37.41983,
    longitude: -122.08544,
    photoUrl: "https://images.unsplash.com/photo-1503376780353-7e6692767b70?auto=format&fit=crop&w=900&q=80",
    make: "Chevrolet",
    model: "Tahoe",
    color: "Blue",
    yearRange: "2016-2019",
  },
];
