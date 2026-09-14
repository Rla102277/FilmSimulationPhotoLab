# Leica v1.2 Ground Truth

Archive SHA-256: `1932cb619aeabe3b63bf616f77ffeac94181fa92af2a189f865068aac8f1e83f`

## Manifest

| ID | Key | Name | Base | Mono | Cube SHA-256 | Icon SHA-256 |
|---:|---|---|---|---|---|---|
| 1001 | `invitation` | IA Invitation | Monochrome (1) | True | `9452ebfd550ce32ffce02077c45900842f42d6ba95e679afc39d0b615c631172` | `8949bdeb210d726b5a4914a0d3b58317793635e4dd49c2b8106f67437ae28a76` |
| 1002 | `witness` | IA Witness | Monochrome (1) | True | `8e26b914ab9e264185b7a27e72bb331e06d831c14d74159ff96bb1b404aaa0b8` | `1f1466ed892323c63afb940195dcd85886500c9b78f129006daaefaefdd88804` |
| 1003 | `zone` | IA Zone | Monochrome (1) | True | `c7a24b78eaf058a39b420de71f1ac19a07ecc3e57b7dee3acc539a2170adc4d9` | `2994d6992aa726da7d9f220241e87aed78df112a1a69cec9e63c35e79bca9a25` |
| 1004 | `presence` | IA Presence | Standard (0) | False | `06dae2aad0db2c84d4f842f6ce08a4bacacc914ea5a94c49060316f60e8c223a` | `1fad7f2536bf9d3c61d7e0250e475675ced971dbcc8f77843136fa50d8aacacd` |
| 1005 | `threshold` | IA Threshold | Standard (0) | False | `d704bcca8b24edb7ab1305bae01419e175d38015ffedd337a2ffc966cb4a50c0` | `108ac5c1c988da48dd2704dde2802c8c9917205eecb632eb0d6d86bab42d7049` |
| 1006 | `americannegative` | IA American Negative | Standard (0) | False | `d2c7aa4e5ae346cc8db8ed4fa2567273f33f5e65e2ab5e3e8708154cce4ecbb1` | `2196a0051d0ead92a1f1bd10490cafa02c8a57f670b3fc572dd0299329e44c68` |
| 1007 | `400h` | IA Kin | Standard (0) | False | `d47bff06bc2130ae7c84f54a1803212830bdf9314b17ca5c94352c582f7d6bce` | `31caa3038027e8bc1ee88d865ca0b22b09dc15d69efa4c10c6662592ceebf35e` |
| 1008 | `natura` | IA Natura | Standard (0) | False | `180e125946c2ccca9513f6b5598a62709a93a0430d6902b0d69fa128c49eeae0` | `de8e13d0868f7abead166d5a2e638ff50e879abc78b3aeef604a19408e690e11` |
| 1009 | `ember` | IA Ember | Standard (0) | False | `78c2fb13ff052d8f022a0eff1cada13d6434b4a4cf15ac253857930508d1de5a` | `2176e0e945e6453db71148666eed54a2a8fe4dd1312831d142b3eacff75dc7cf` |

## Actual package notes

- v1.2 contains nine installed Looks.
- Slot 1007 changed from IA 400H to **IA Kin**.
- Kin has an Agfa alternative for comparison that is not installed by default.
- The package README states the other eight Looks are preserved from v1.1.
- The package includes Natura source mapping, validation analysis, Kin comparison artifacts, `uploader.py`, and self-contained `ia_final9_upload_pyto.py`.
- The package itself remains the final authority if this document and the archive ever disagree.
