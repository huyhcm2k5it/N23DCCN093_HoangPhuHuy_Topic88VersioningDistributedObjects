# Frontend Dashboard

React dashboard cho Topic 88: Versioning Distributed Objects.

## Tabs

- Overview & Metrics: xem benchmark Full Snapshot vs Delta Storage.
- Distributed Sites: xem 3 site, fragmentation, object hiện có.
- Conflict Demo: demo 2 site checkout cùng object và checkin tạo conflict branch.
- Failure Demo: demo node disconnect, outbox retry và idempotent inbox.

## Run

```bash
npm install
npm run dev
```

Backend cần chạy trước:

```bash
python main.py --servers
```

## Code Map

- `src/App.jsx`: tab layout và polling trạng thái site.
- `src/api.js`: các hàm gọi REST API.
- `src/components/TabOverview.jsx`: benchmark và lý thuyết delta.
- `src/components/TabDashboard.jsx`: object/site dashboard.
- `src/components/TabConflict.jsx`: conflict branching demo.
- `src/components/TabNetworkDisconnect.jsx`: network failure + outbox retry demo.
