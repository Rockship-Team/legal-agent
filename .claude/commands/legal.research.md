---
description: Research Vietnamese laws and legal requirements for any topic
---

## User Input

```text
$ARGUMENTS
```

## Purpose

Tim hieu luat phap Viet Nam ve bat ky chu de nao. Huu ich khi:
- Muon hieu luat truoc khi tao hop dong
- Can biet yeu cau phap ly cho mot loai giao dich
- Muon tim dieu luat cu the

## Workflow

### Step 1: Xac dinh chu de

Neu `$ARGUMENTS` rong, hoi nguoi dung:

```
Ban muon tim hieu phap luat ve van de gi?

Vi du: hop dong thue nha, chuyen nhuong dat, thanh lap cong ty, ly hon, thua ke, ...
```

### Step 2: Search thong tin

Thuc hien nhieu search queries de tim day du thong tin:

1. **Luat ap dung:**
   - `"[chu de] theo luat Viet Nam"`
   - `"Bo luat Dan su 2015 [chu de]"`
   - `"Luat [lien quan] [nam moi nhat]"`

2. **Yeu cau cu the:**
   - `"dieu kien [chu de] theo phap luat"`
   - `"thu tuc [chu de] Viet Nam"`
   - `"ho so can thiet [chu de]"`

3. **Mau va vi du:**
   - `"mau [loai van ban] theo phap luat Viet Nam"`
   - `"vi du [chu de] thuc te"`

### Step 3: Tong hop ket qua

Trinh bay ket qua theo format:

```
## Phap luat ve [Chu de]

### Cac luat ap dung
- **[Ten luat]**: Dieu X, Y, Z
- **[Ten luat khac]**: Dieu A, B

### Dieu kien phap ly
1. [Dieu kien 1]
2. [Dieu kien 2]
...

### Cac giay to/thong tin can thiet
- [Giay to 1]
- [Giay to 2]
...

### Luu y quan trong
- [Luu y 1]
- [Luu y 2]

### Nguon tham khao
- [Link 1]
- [Link 2]
```

### Step 4: Hoi tiep

Sau khi trinh bay, hoi:

```
Ban co muon:
- Tim hieu them chi tiet nao khong?
- Tao hop dong lien quan? (chay /legal.create-contract)
```

## Conversation Style

- Trinh bay ro rang, de hieu
- Ghi ro dieu luat cu the (Dieu so may, Luat gi, nam nao)
- Neu khong chac chan, thong bao la thong tin tham khao

## Error Handling

- Neu khong tim duoc thong tin, thong bao va de nghi nguoi dung cung cap them chi tiet
- Neu chu de khong ro rang, hoi lai de lam ro
