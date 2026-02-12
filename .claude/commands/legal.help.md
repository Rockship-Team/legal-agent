---
description: Display all available Legal Chatbot commands with descriptions
---

## Legal Chatbot Commands

Cac lenh ho tro tao va quan ly hop dong phap ly:

### Tao hop dong
| Lenh | Mo ta |
|------|-------|
| `/legal.create-contract` | Tao hop dong moi - tu dong research luat truoc khi hoi thong tin |

### Nghien cuu phap ly
| Lenh | Mo ta |
|------|-------|
| `/legal.research [topic]` | Tim hieu luat phap Viet Nam ve bat ky chu de nao |

### Quan ly hop dong
| Lenh | Mo ta |
|------|-------|
| `/legal.preview` | Xem truoc hop dong tren trinh duyet |
| `/legal.export-pdf` | Xuat hop dong ra file PDF |

### Data Pipeline
| Lenh | Mo ta |
|------|-------|
| `/legal.pipeline crawl [category]` | Crawl va index van ban phap luat theo linh vuc |
| `/legal.pipeline categories` | Liet ke cac linh vuc co san (dat_dai, nha_o, ...) |
| `/legal.pipeline status` | Kiem tra trang thai pipeline |

### Database
| Lenh | Mo ta |
|------|-------|
| `/legal.db status` | Kiem tra ket noi database va thong ke |
| `/legal.db migrate` | Migrate schema (Supabase hoac SQLite) |

### Audit Trail
| Lenh | Mo ta |
|------|-------|
| `/legal.audit list` | Xem lich su research va contract gan day |
| `/legal.audit show [id]` | Xem chi tiet mot audit entry |
| `/legal.audit verify [id]` | Kiem tra luat da dung con hieu luc khong |

## Huong dan su dung

### Tao hop dong moi
1. Chay `/legal.create-contract`
2. Nhap loai hop dong (thue nha, mua ban dat, lao dong, ...)
3. Bot se tu dong research luat lien quan
4. Tra loi tung cau hoi de dien thong tin
5. Chay `/legal.preview` de xem truoc
6. Chay `/legal.export-pdf` de xuat file PDF

### Tim hieu phap luat
1. Chay `/legal.research [chu de]`
2. Bot se search va tong hop thong tin phap luat
3. Co the hoi them chi tiet sau khi xem ket qua

### Crawl du lieu phap luat moi
1. Chay `/legal.db status` de kiem tra ket noi
2. Chay `/legal.pipeline categories` de xem linh vuc co san
3. Chay `/legal.pipeline crawl dat_dai` de crawl luat dat dai
4. Chay `/legal.audit list` de xem ket qua

## Vi du

```
/legal.create-contract thue nha
/legal.create-contract mua ban dat
/legal.research thanh lap cong ty TNHH
/legal.research thu tuc ly hon
/legal.pipeline crawl dat_dai
/legal.pipeline crawl dat_dai --limit 5
/legal.db status
/legal.audit list --limit 10
/legal.audit verify a1b2c3
```

## Luu y

- Day chi la cong cu ho tro, khong thay the tu van phap ly chuyen nghiep
- Cac hop dong can duoc kiem tra boi luat su truoc khi su dung
- Thong tin phap luat duoc research tu internet, can kiem chung truoc khi ap dung
