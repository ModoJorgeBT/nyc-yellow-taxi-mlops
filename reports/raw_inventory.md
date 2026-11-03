# Inventario local de Parquet — 2024 y 2025

Observación: 2026-11-03, America/Costa_Rica. Revisión adicional autorizada junto a T03.

Se observaron 24 archivos, 1,522,975,012 bytes (1.418 GiB) y 89,892,322 filas declaradas en sus footers. Lectura con PyArrow 26.0.1.

Se reorganizaron desde raw directamente a `data/raw/YYYY/MM/` sin cambiar nombres ni contenido. SHA-256 comprobado antes y después para los 24 archivos; no hubo sobrescrituras.

La cobertura se identifica por nombre de archivo: enero a diciembre de ambos años. No demuestra que todas las fechas de las filas correspondan a ese mes. El esquema y el conteo proceden de metadatos Parquet; no se escanearon filas, no se verificó la integridad de todas las páginas ni se calcularon métricas de calidad o del target.

Archivos locales aportados por el usuario; URL y fecha de descarga no verificadas.

Este inventario no sustituye al manifiesto de ingesta ni aprueba D-01/D-04. No se asignaron 2024/2025 a train/validación/test. El perfilado EDA y los Quality Gates continúan en sus tareas futuras.

## Archivos

| Año/mes | Ruta | Bytes | Filas del footer | Columnas | Grupos de filas |
|---|---|---:|---:|---:|---:|
| 2024-01 | `data/raw/2024/01/yellow_tripdata_2024-01.parquet` | 49961641 | 2964624 | 19 | 3 |
| 2024-02 | `data/raw/2024/02/yellow_tripdata_2024-02.parquet` | 50349284 | 3007526 | 19 | 3 |
| 2024-03 | `data/raw/2024/03/yellow_tripdata_2024-03.parquet` | 60078280 | 3582628 | 19 | 4 |
| 2024-04 | `data/raw/2024/04/yellow_tripdata_2024-04.parquet` | 59133625 | 3514289 | 19 | 4 |
| 2024-05 | `data/raw/2024/05/yellow_tripdata_2024-05.parquet` | 62553128 | 3723833 | 19 | 4 |
| 2024-06 | `data/raw/2024/06/yellow_tripdata_2024-06.parquet` | 59859922 | 3539193 | 19 | 4 |
| 2024-07 | `data/raw/2024/07/yellow_tripdata_2024-07.parquet` | 52299432 | 3076903 | 19 | 3 |
| 2024-08 | `data/raw/2024/08/yellow_tripdata_2024-08.parquet` | 51067350 | 2979183 | 19 | 3 |
| 2024-09 | `data/raw/2024/09/yellow_tripdata_2024-09.parquet` | 61170186 | 3633030 | 19 | 4 |
| 2024-10 | `data/raw/2024/10/yellow_tripdata_2024-10.parquet` | 64346071 | 3833771 | 19 | 4 |
| 2024-11 | `data/raw/2024/11/yellow_tripdata_2024-11.parquet` | 60658709 | 3646369 | 19 | 4 |
| 2024-12 | `data/raw/2024/12/yellow_tripdata_2024-12.parquet` | 61524085 | 3668371 | 19 | 4 |
| 2025-01 | `data/raw/2025/01/yellow_tripdata_2025-01.parquet` | 59158238 | 3475226 | 20 | 4 |
| 2025-02 | `data/raw/2025/02/yellow_tripdata_2025-02.parquet` | 60343086 | 3577543 | 20 | 4 |
| 2025-03 | `data/raw/2025/03/yellow_tripdata_2025-03.parquet` | 69964745 | 4145257 | 20 | 4 |
| 2025-04 | `data/raw/2025/04/yellow_tripdata_2025-04.parquet` | 67352824 | 3970553 | 20 | 4 |
| 2025-05 | `data/raw/2025/05/yellow_tripdata_2025-05.parquet` | 77837865 | 4591845 | 20 | 5 |
| 2025-06 | `data/raw/2025/06/yellow_tripdata_2025-06.parquet` | 73542954 | 4322960 | 20 | 5 |
| 2025-07 | `data/raw/2025/07/yellow_tripdata_2025-07.parquet` | 66943728 | 3898963 | 20 | 4 |
| 2025-08 | `data/raw/2025/08/yellow_tripdata_2025-08.parquet` | 62293743 | 3574091 | 20 | 4 |
| 2025-09 | `data/raw/2025/09/yellow_tripdata_2025-09.parquet` | 72432945 | 4251015 | 20 | 5 |
| 2025-10 | `data/raw/2025/10/yellow_tripdata_2025-10.parquet` | 75267589 | 4428699 | 20 | 5 |
| 2025-11 | `data/raw/2025/11/yellow_tripdata_2025-11.parquet` | 71134255 | 4181444 | 20 | 4 |
| 2025-12 | `data/raw/2025/12/yellow_tripdata_2025-12.parquet` | 73701327 | 4305006 | 20 | 5 |

## Esquemas observados

La huella se calcula con nombres, tipos y nulabilidad, sin metadatos personalizados. Describe diferencias; no es todavía el contrato aprobado de T08.

Se observaron dos grupos uniformes por año: 19 columnas en 2024 y 20 en 2025. La columna añadida en 2025 es `cbd_congestion_fee`; no se observaron columnas eliminadas ni cambios de tipo entre campos compartidos. Es un cargo final y no se autoriza como predictor. Los timestamps del esquema son `timestamp[us]` sin zona horaria declarada; la política histórica de zona/DST sigue pendiente.

Filas declaradas por año: 41,169,720 en 2024 y 48,722,602 en 2025. No se interpretan esos conteos como filas válidas para modelado.

### Huella `ca4db4678865af903dfc21224cd567df007e39fb489f3ca99e76edb6616d2457`

Archivos: `yellow_tripdata_2024-01.parquet`, `yellow_tripdata_2024-02.parquet`, `yellow_tripdata_2024-03.parquet`, `yellow_tripdata_2024-04.parquet`, `yellow_tripdata_2024-05.parquet`, `yellow_tripdata_2024-06.parquet`, `yellow_tripdata_2024-07.parquet`, `yellow_tripdata_2024-08.parquet`, `yellow_tripdata_2024-09.parquet`, `yellow_tripdata_2024-10.parquet`, `yellow_tripdata_2024-11.parquet`, `yellow_tripdata_2024-12.parquet`.

| Campo | Tipo Arrow | Nullable |
|---|---|---|
| `VendorID` | `int32` | True |
| `tpep_pickup_datetime` | `timestamp[us]` | True |
| `tpep_dropoff_datetime` | `timestamp[us]` | True |
| `passenger_count` | `int64` | True |
| `trip_distance` | `double` | True |
| `RatecodeID` | `int64` | True |
| `store_and_fwd_flag` | `large_string` | True |
| `PULocationID` | `int32` | True |
| `DOLocationID` | `int32` | True |
| `payment_type` | `int64` | True |
| `fare_amount` | `double` | True |
| `extra` | `double` | True |
| `mta_tax` | `double` | True |
| `tip_amount` | `double` | True |
| `tolls_amount` | `double` | True |
| `improvement_surcharge` | `double` | True |
| `total_amount` | `double` | True |
| `congestion_surcharge` | `double` | True |
| `Airport_fee` | `double` | True |

### Huella `ac74c44b1b7b48603a88ff80f9d91db6d0cfb89f8e78f6fe33e9fa15128816c7`

Archivos: `yellow_tripdata_2025-01.parquet`, `yellow_tripdata_2025-02.parquet`, `yellow_tripdata_2025-03.parquet`, `yellow_tripdata_2025-04.parquet`, `yellow_tripdata_2025-05.parquet`, `yellow_tripdata_2025-06.parquet`, `yellow_tripdata_2025-07.parquet`, `yellow_tripdata_2025-08.parquet`, `yellow_tripdata_2025-09.parquet`, `yellow_tripdata_2025-10.parquet`, `yellow_tripdata_2025-11.parquet`, `yellow_tripdata_2025-12.parquet`.

| Campo | Tipo Arrow | Nullable |
|---|---|---|
| `VendorID` | `int32` | True |
| `tpep_pickup_datetime` | `timestamp[us]` | True |
| `tpep_dropoff_datetime` | `timestamp[us]` | True |
| `passenger_count` | `int64` | True |
| `trip_distance` | `double` | True |
| `RatecodeID` | `int64` | True |
| `store_and_fwd_flag` | `large_string` | True |
| `PULocationID` | `int32` | True |
| `DOLocationID` | `int32` | True |
| `payment_type` | `int64` | True |
| `fare_amount` | `double` | True |
| `extra` | `double` | True |
| `mta_tax` | `double` | True |
| `tip_amount` | `double` | True |
| `tolls_amount` | `double` | True |
| `improvement_surcharge` | `double` | True |
| `total_amount` | `double` | True |
| `congestion_surcharge` | `double` | True |
| `Airport_fee` | `double` | True |
| `cbd_congestion_fee` | `double` | True |

## Integridad durante la organización

Estos hashes acreditan conservación de los archivos aportados durante el movimiento; no los comparan con una publicación oficial remota.

| Archivo | SHA-256 antes y después |
|---|---|
| `yellow_tripdata_2024-01.parquet` | `C4D59DA7BBC8ABAEEEB1727947EE93D9891A71ACB42854BD80DB1571B2030510` |
| `yellow_tripdata_2024-02.parquet` | `C76C43C18C6C6664080DD920BAAB4928988D5786A6B65980792CA7CD796F9F20` |
| `yellow_tripdata_2024-03.parquet` | `2D4CDC8FB96726CDD3803B13B02D2E61E71D45720AFF0EBC693A8BDD1F249823` |
| `yellow_tripdata_2024-04.parquet` | `CE37F736C7CF9E92164C850EF2B502A8F7BB590FC1804B6EDBCB80293DA01B89` |
| `yellow_tripdata_2024-05.parquet` | `1974230BE2B5A3EA92E47B5EB77F32DBF1DE896D81AD8DF4AB6FABA52749AD23` |
| `yellow_tripdata_2024-06.parquet` | `677CF14C8347F745B583F012FBDBA072334C6C4EFA17BFD6A64369F2BA30329C` |
| `yellow_tripdata_2024-07.parquet` | `AF12D6B04DAEB78550799AE99933D495B27D715B6DBB0FAD9BB750A4537D3070` |
| `yellow_tripdata_2024-08.parquet` | `7315643DD16BAFC03E27D9903EDBFD35404C2550A695D0DA0A3E73852D940CFB` |
| `yellow_tripdata_2024-09.parquet` | `2F42E4A383A6635DE803001462848D0AEE2B47F6CE899126805D2D05361FB843` |
| `yellow_tripdata_2024-10.parquet` | `D19FE05AA0B259AF24EB47051735293287F1E6DC263BA04030EC1AB4C6EC2650` |
| `yellow_tripdata_2024-11.parquet` | `5EF321876DE5007A7C147A347389133FC94FD7AC28F82EB1D57D8F2CF05CFD3B` |
| `yellow_tripdata_2024-12.parquet` | `41EBF7DB80BEBDE60C58E5143C14CDF38AD04A0F3E3FF44215B3E240D55F6C78` |
| `yellow_tripdata_2025-01.parquet` | `9AF277E4C0D3F9DEB30644DA822981E1E7DF6AF58313170FD3AA8A474485488A` |
| `yellow_tripdata_2025-02.parquet` | `037CBA555A73663F3A51A2C27816E40E3FEB364769942BDF122B9DA31E377BD3` |
| `yellow_tripdata_2025-03.parquet` | `20C4B77CCE457B7CFDAE77C5069CA7DC91C167F876A41467F4502AB69487A186` |
| `yellow_tripdata_2025-04.parquet` | `6F98938DE9380A3F85600533816F0DC0E6D9B5B210E485D623952BAC599BBE28` |
| `yellow_tripdata_2025-05.parquet` | `7EF46BCD0FCEEE7F8C0BB38A532BE05BCEEFABB512D4BB0B32A7727DD862B15C` |
| `yellow_tripdata_2025-06.parquet` | `1BEA7F5B09C744414451FA7FEF09FBC5A393FFB1621C859BE6BA0DF23A14E1B6` |
| `yellow_tripdata_2025-07.parquet` | `1EFA6A0458DC60341F7F81DCBB5015AF731F42D1A109F4E0D594DD46970FD4EF` |
| `yellow_tripdata_2025-08.parquet` | `B982ACE703E3564D92E94EDAE5EC93515F4F1FB07A5B95E7404C32464C1A6A89` |
| `yellow_tripdata_2025-09.parquet` | `CD39B9901F01D1FD752D45CBAEC91EE5F68C4DDDF9E261E938C1DBAB404644C7` |
| `yellow_tripdata_2025-10.parquet` | `E1F63CAF331BC6230D9C6F757CB88E55FDC2BDDDE185FB414D2C947ABDC773C3` |
| `yellow_tripdata_2025-11.parquet` | `2CF2F3127F96D4D5DEA30F8AFE05119CF8E4BA57BD9E60B789D3F296FC8459AB` |
| `yellow_tripdata_2025-12.parquet` | `EABA7FF61EBB6453FC6F673FDA43D621380307F869B768B124992E8486C785E1` |
