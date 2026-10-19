#!/usr/bin/env python3
"""
Independent SunNXT Master Generator
Generates full SunNXT linear channel playlist (33+ channels) with ClearKeys and DASH MPD manifests.
Independent of third-party playlist upstreams.
"""

import os
import sys
import re
import json
from datetime import datetime, timezone, timedelta

# Ensure UTF-8 output
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

IST = timezone(timedelta(hours=5, minutes=30))

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_M3U = os.path.join(ROOT_DIR, "playlists", "sunnxt.m3u")

# Complete catalog of SunNXT Channels with MPD manifests and ClearKeys
SUNNXT_CHANNELS = [
    {
        "id": "sun-194408",
        "name": "Sun TV",
        "logo": "https://sund-images.sunnxt.com/194408/640x360_SunTV_194408_2617a80e-4f90-42fa-b13a-acc8d7c97f9e.jpg",
        "key": "6752015acf084572a08dfe21796f8b45:ff823ddbe5625c35d3e93f0ed4520115",
        "url": "https://livestream1.sunnxt.com/05b5df1221764bca9867054c5e65ee62/SunTVB_IN_index.mpd"
    },
    {
        "id": "sun-194403",
        "name": "Sun TV HD",
        "logo": "https://sund-images.sunnxt.com/194403/640x360_SunTVHD_194403_522c701c-4770-4934-a6d3-47045b0d4fa5.jpg",
        "key": "3891557f1cb14dedb7545bf52499d748:fb662f742e5f5e0c61a7c1c66d2b019a",
        "url": "https://livestream2.sunnxt.com/19ee29194c4d4fc286c3e697362e60cd/SunTVHDB_IN_index.mpd"
    },
    {
        "id": "sun-194403-dv",
        "name": "Sun TV HD - Dolby Vision",
        "logo": "https://sund-images.sunnxt.com/195491/640x360_SunTVHDDolbyVision_195491_8110232c-dd00-4dbe-98ff-25bf5fe8749e.jpg",
        "key": "3891557f1cb14dedb7545bf52499d748:fb662f742e5f5e0c61a7c1c66d2b019a",
        "url": "https://livestream2.sunnxt.com/19ee29194c4d4fc286c3e697362e60cd/SunTVHDB_IN_index.mpd"
    },
    {
        "id": "sun-194387",
        "name": "Sun Marathi",
        "logo": "https://sund-images.sunnxt.com/194387/640x360_SunMarathi_194387_441db2e2-0fa1-48ca-be59-7f5dd70f66cb.jpg",
        "key": "5ea90a1f3b1e4a0a9b72c8e0f4a9bf31:30899fda5ca4dfb5a4535ce10c4d7341",
        "url": "https://livestream9.sunnxt.com/b0aacde03b744564870634ecb10e8a31/SunMarathiB_IN_index.mpd"
    },
    {
        "id": "sun-194406",
        "name": "Sun Music HD",
        "logo": "https://sund-images.sunnxt.com/194406/640x360_SunMusicHD_194406_87e8d029-f695-477c-9ace-a3c2cbe15004.jpg",
        "key": "b5a2c6d13b9748de9ceebc0a8adc8af3:e806fec1bf1c8a844216118c94bad020",
        "url": "https://livestream.sunnxt.com/d434796d90fa4dc9b7ecfacedbe683f1/SunMusicHDB_IN_index.mpd"
    },
    {
        "id": "sun-194410",
        "name": "Sun Music",
        "logo": "https://sund-images.sunnxt.com/194410/640x360_SunMusic_194410_d4d08876-9d23-432c-aab4-b5c70c58aaac.jpg",
        "key": "21ddc14c4da94c079d4f4c343ecdcd80:5701bee4ee9b625d0c8ed7de032a7478",
        "url": "https://livestream.sunnxt.com/585bb66e95c84ccea3f828c96b3567b5/SunMusicB_IN_index.mpd"
    },
    {
        "id": "sun-194391",
        "name": "Sun Life",
        "logo": "https://sund-images.sunnxt.com/194391/640x360_SunLife_194391_d407948a-b7a2-4a1f-8409-56f7261cefa1.jpg",
        "key": "81546df3f41c4a6dbc9a4efc7f2fb626:3928505f4054cf1fa935276fdbe40992",
        "url": "https://livestream.sunnxt.com/d33cf7d91cb64b22b10a2bb1e8979188/SunLifeB_IN_index.mpd"
    },
    {
        "id": "sun-194404",
        "name": "Sun News",
        "logo": "https://sund-images.sunnxt.com/194404/640x360_SunNews_194404_0af09ceb-cb6f-48e6-9f5c-395749f0fcee.jpg",
        "key": "4df8f920386e4346ba6b7d7ae935d668:c5fcaa8df5663365d938a50987f71b84",
        "url": "https://livestream.sunnxt.com/39ffda2369664da0915ee5164d7dfeb6/SunNewsB_IN_index.mpd"
    },
    {
        "id": "sun-194409",
        "name": "KTV",
        "logo": "https://sund-images.sunnxt.com/194409/640x360_KTV_194409_91b39445-b996-4e46-bafa-b78548e4da2e.jpg",
        "key": "426117d115b04497b0b0d425e8095184:aa751ae8a41ac6f87141734163ffe3b2",
        "url": "https://livestream.sunnxt.com/3b827e8574164b8bb26c3046f45a30ce/KTVB_IN_index.mpd"
    },
    {
        "id": "sun-194405",
        "name": "KTV HD",
        "logo": "https://sund-images.sunnxt.com/194405/640x360_KTVHD_194405_34eec3b6-2e21-4f10-9fc6-943e8bb5f7b8.jpg",
        "key": "351e547391bb45cbac66d2cb9ec0c294:3bd646753f4903eee3b404646c7819d3",
        "url": "https://livestream7.sunnxt.com/7b134eb9236c4b2ebff7dc8ae5113d50/KTVHDB_IN_index.mpd"
    },
    {
        "id": "sun-194389",
        "name": "Gemini TV",
        "logo": "https://sund-images.sunnxt.com/194389/640x360_GeminiTV_194389_cf2ddb86-1d12-426b-80ee-c5b76e1871a2.jpg",
        "key": "89eb511b846e4b9bbd514efec832b842:3fc28a7e780fe3a3b5a1b32d207ec295",
        "url": "https://livestream3.sunnxt.com/fcfe0f6e14a141dc8a26ef53ba0f5904/GeminiTVB_IN_index.mpd"
    },
    {
        "id": "sun-194388",
        "name": "Gemini TV HD",
        "logo": "https://sund-images.sunnxt.com/194388/640x360_GeminiTVHD_194388_704bf2d0-a359-42b7-a357-e6f98797f7bb.jpg",
        "key": "aa3a6a9ff2a344d59bc656a2fa56efb7:02ae80ff63efd0ebbf94c77c68a44b1c",
        "url": "https://livestream15.sunnxt.com/b971a9386d914d9bba142079a473fbe5/GeminiTVHDB_IN_index.mpd"
    },
    {
        "id": "sun-194388-dv",
        "name": "Gemini TV HD - Dolby Vision",
        "logo": "https://sund-images.sunnxt.com/195493/640x360_GeminiTVHDDolbyVision_195493_e128185c-197e-40e1-ad76-2182b7cf537d.jpg",
        "key": "aa3a6a9ff2a344d59bc656a2fa56efb7:02ae80ff63efd0ebbf94c77c68a44b1c",
        "url": "https://livestream15.sunnxt.com/b971a9386d914d9bba142079a473fbe5/GeminiTVHDB_IN_index.mpd"
    },
    {
        "id": "sun-194386",
        "name": "Gemini Movies",
        "logo": "https://sund-images.sunnxt.com/194386/640x360_GeminiMovies_194386_2bc5b6fa-90f7-4180-a8dc-94732ca4a480.jpg",
        "key": "86df6834dd9b418fa7b2a95c9ee17228:22729a6cf7639f72c0c7a5f0cf5638eb",
        "url": "https://livestream6.sunnxt.com/269fe01460164db69fdf55f307e594d4/GeminiMoviesB_IN_index.mpd"
    },
    {
        "id": "sun-194385",
        "name": "Gemini Movies HD",
        "logo": "https://sund-images.sunnxt.com/194385/640x360_GeminiMoviesHD_194385_160352ef-39fe-443b-8515-3ce367464a4b.jpg",
        "key": "7bbf3e20e88c42b78a9c372b6efcf83f:5aa30fe186e8da6fceaa98a7a2fa7f90",
        "url": "https://livestream16.sunnxt.com/d560c5a242d04a79b2fa9f45d475659b/GeminiMoviesHDB_IN_index.mpd"
    },
    {
        "id": "sun-194384",
        "name": "Gemini Music",
        "logo": "https://sund-images.sunnxt.com/194384/640x360_GeminiMusic_194384_be5240bc-a96c-4861-a590-c274296df44d.jpg",
        "key": "f08819beebf54a8ea6709dd8d8b92b6a:f948f9dddb0a59a7f340274ee8fcdae3",
        "url": "https://livestream.sunnxt.com/6249cbe5d53a4733aeebcc634d1bc945/GeminiMusicB_IN_index.mpd"
    },
    {
        "id": "sun-194383",
        "name": "Gemini Music HD",
        "logo": "https://sund-images.sunnxt.com/194383/640x360_GeminiMusicHD_194383_c5aa2918-6c8a-4bb5-905c-cf57cb0fca56.jpg",
        "key": "2fe955871f764a57b2518aeb5a289053:a537f59d2a6a12bfd38d9d443db487f9",
        "url": "https://livestream4.sunnxt.com/37ca06fcf1894d0ca962c079be870da3/GeminiMusicHDB_IN_index.mpd"
    },
    {
        "id": "sun-194392",
        "name": "Gemini Comedy",
        "logo": "https://sund-images.sunnxt.com/194392/640x360_GeminiComedy_194392_7c5148fb-be86-4c4f-9e32-2d13bc499bfa.jpg",
        "key": "12fc57a159ea426fa16503c4cf7fce29:c46b5a32b6e159aa960fc5d4ca810c95",
        "url": "https://livestream14.sunnxt.com/d96e579290fa415bb68ca47c05b8a6a6/GeminiComedyB_IN_index.mpd"
    },
    {
        "id": "sun-194382",
        "name": "Udaya TV",
        "logo": "https://sund-images.sunnxt.com/194382/640x360_UdayaTV_194382_d741cb33-2895-46f9-aa11-8fcb7c4d51b5.jpg",
        "key": "08b044d715d141e6a2b85295cbb46755:0fc8654a938c8230b427845fc867a5b3",
        "url": "https://livestream.sunnxt.com/4925821da42a42b1a786e2467d1656bc/UdayaTVB_IN_index.mpd"
    },
    {
        "id": "sun-194381",
        "name": "Udaya TV HD",
        "logo": "https://sund-images.sunnxt.com/194381/640x360_UdayaTVHD_194381_c21fec52-c3f2-45e0-8fa7-aa828a2b5357.jpg",
        "key": "e30ae18bf14945d8b67b1cb1e73e13d5:128b9d0738a9d18fa78083bf23631da7",
        "url": "https://livestream.sunnxt.com/02330a911eb84ef0ae39f99d8d179d63/UdayaTVHDB_IN_index.mpd"
    },
    {
        "id": "sun-194379",
        "name": "Udaya Movies",
        "logo": "https://sund-images.sunnxt.com/194379/640x360_UdayaMovies_194379_48b813b2-6014-411a-abaf-e991277a0bf9.jpg",
        "key": "52ba48bbafb042c18d36fc31b26639c0:693c0429f9c73efd8065099cb6a012a6",
        "url": "https://livestream.sunnxt.com/7b94157ffddb4d9fae7c2ba3ee63ce09/UdayaMoviesB_IN_index.mpd"
    },
    {
        "id": "sun-194380",
        "name": "Udaya Music",
        "logo": "https://sund-images.sunnxt.com/194380/640x360_UdayaMusic_194380_f02279b9-d2d4-4cf7-9a99-cf36551b9e07.jpg",
        "key": "05be0568ff1a4a15998a96e95bfcfc11:d9396bf8e1e779a5b6c813be6a1c8b3d",
        "url": "https://livestream.sunnxt.com/b282713f0ce34559b92200be643a6703/UdayaMusicB_IN_index.mpd"
    },
    {
        "id": "sun-194378",
        "name": "Surya TV",
        "logo": "https://sund-images.sunnxt.com/194378/640x360_SuryaTV_194378_24be26c6-943f-4e00-a616-e5ff75f6d895.jpg",
        "key": "ab83ff558ba347318ff20626fcce320a:95a6ee98322c34cb2f207a976dfbf771",
        "url": "https://livestream.sunnxt.com/00d3e521e10d481aa52b1b6cf1b5fc91/SuryaTVB_IN_index.mpd"
    },
    {
        "id": "sun-194377",
        "name": "Surya TV HD",
        "logo": "https://sund-images.sunnxt.com/194377/640x360_SuryaTVHD_194377_1e68c17b-6a5d-45ba-b0ce-d4a89a08ebfc.jpg",
        "key": "cb08bf78ee7740e6b83fecf8ebc70233:d1c3a6473dfb489953257f8976bcf641",
        "url": "https://livestream.sunnxt.com/8f895fb976e147d39d91f24ecdc733ad/SuryaTVHDB_IN_index.mpd"
    },
    {
        "id": "sun-194376",
        "name": "Surya Movies",
        "logo": "https://sund-images.sunnxt.com/194376/640x360_SuryaMovies_194376_2b3fb262-e64e-4f05-8e7c-a4ec0e27163a.jpg",
        "key": "dfb091f1739c4a8aa522c0c73322b7bf:0a58fa4d9b15bc5eb24c7f04dfc0f00c",
        "url": "https://livestream.sunnxt.com/ae6b35398ddb4352b2f6ef5752697a0a/SuryaMoviesB_IN_index.mpd"
    },
    {
        "id": "sun-194375",
        "name": "Surya Music",
        "logo": "https://sund-images.sunnxt.com/194375/640x360_SuryaMusic_194375_f7fc32d8-21d1-44eb-b6df-2030d31dfc95.jpg",
        "key": "7b2ef446168641a2ba37a505bdf9f939:eb6e06a7c6f0928ff4be7ba9a41ee941",
        "url": "https://livestream.sunnxt.com/0f6b490d1fe3438e93aa2925b4105ca2/SuryaMusicB_IN_index.mpd"
    },
    {
        "id": "sun-194374",
        "name": "Surya Comedy",
        "logo": "https://sund-images.sunnxt.com/194374/640x360_SuryaComedy_194374_45b41bc1-25e2-4522-83b6-e2fcb4308573.jpg",
        "key": "a822002166dc4463a8a370e060c5a297:489ee0f1be569107954e3f3b92f4477b",
        "url": "https://livestream.sunnxt.com/cb0c2c1913ef45ceb8b5e28a5d3f2716/SuryaComedyB_IN_index.mpd"
    },
    {
        "id": "sun-194393",
        "name": "Gemini Life",
        "logo": "https://sund-images.sunnxt.com/194393/640x360_GeminiLife_194393_7a965701-a189-4b68-b765-a8ca090e9d48.jpg",
        "key": "96d5157791ea4817a66a419e285a137f:d6d0ad2a9a6cc56e18d7557c7c693a37",
        "url": "https://livestream.sunnxt.com/a4b4f71a8b4344f3a280e906657a517a/GeminiLifeB_IN_index.mpd"
    },
    {
        "id": "sun-194407",
        "name": "Adithya TV",
        "logo": "https://sund-images.sunnxt.com/194407/960x540_AdithyaTV_194407_b6f8fa30-255b-4f4a-8f8f-4264abda8b33.jpg",
        "key": "d674a1a7f43641a29bd8867d87c7259a:812f55dcde68619fc6ad95951b241d2c",
        "url": "https://livestream.sunnxt.com/4d0eb3cde30247ada4ade679fdfbaf86/AdithyaTVB_IN_index.mpd"
    },
    {
        "id": "sun-194346",
        "name": "Kushi TV",
        "logo": "https://sund-images.sunnxt.com/194346/960x540_KushiTV_194346_b0eff97b-4670-42fb-9d87-49d78fab6f3a.jpg",
        "key": "e16421cf7c374c57a8f7e91049f58cd9:b7e01aba2c307b1f05057e91a9d150d2",
        "url": "https://livestream.sunnxt.com/4a736d41608849758a0aed36949ded30/KushiTVB_IN_index.mpd"
    },
    {
        "id": "sun-194390",
        "name": "Chutti TV",
        "logo": "https://sund-images.sunnxt.com/194390/640x360_ChuttiTV_194390_61005292-313a-45b4-b6a8-3ac5128a513e.jpg",
        "key": "05da38a46fb7403088f41434e44de980:488046139a1e1d65323cfe4bb1b30b7b",
        "url": "https://livestream.sunnxt.com/3ed29d5b01b546eaa05d184cd87535f1/ChuttiTVB_IN_index.mpd"
    },
    {
        "id": "sun-194348",
        "name": "Kochu TV",
        "logo": "https://sund-images.sunnxt.com/194348/960x540_KochuTV_194348_9777cbfd-685b-4e06-a7cc-f2902c1874e8.jpg",
        "key": "7354fb333b0c4159bc6c433c4db13d0f:fbf8b4a11febf7d2eed2283006979176",
        "url": "https://livestream.sunnxt.com/1893b9ab790747cb80a584873a608dcb/KochuTVB_IN_index.mpd"
    },
    {
        "id": "sun-194347",
        "name": "Chintu TV",
        "logo": "https://sund-images.sunnxt.com/194347/960x540_ChintuTV_194347_64af5425-0ed0-4c8a-b071-00ef86eaefde.jpg",
        "key": "19d8a5cc002f411b89b33925acdc33e0:2a9aa7a3f69834c4f348430cc3f658bb",
        "url": "https://livestream.sunnxt.com/ed4c67ad957644b69361651d9101107e/ChintuTVB_IN_index.mpd"
    }
]

def generate_playlist():
    now_ist = datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S IST")
    lines = [
        "#EXTM3U",
        f"#DATE:- {now_ist}",
        f"# Category: SunNXT",
        f"# Total Channels: {len(SUNNXT_CHANNELS)}",
        ""
    ]

    for ch in SUNNXT_CHANNELS:
        lines.append(
            f'#EXTINF:-1 tvg-id="{ch["id"]}" tvg-name="{ch["name"]}" tvg-logo="{ch["logo"]}" '
            f'group-title="SunNXT" group-logo="https://upload.wikimedia.org/wikipedia/en/d/d5/Sun_NXT_logo_small.png" type="dash",{ch["name"]}'
        )
        lines.append("#KODIPROP:inputstream=inputstream.adaptive")
        lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")
        lines.append("#KODIPROP:inputstream.adaptive.license_type=org.w3.clearkey")
        lines.append(f'#KODIPROP:inputstream.adaptive.license_key={ch["key"]}')
        lines.append("#EXTVLCOPT:http-user-agent=plaYtv/7.1.5 (Linux;Android 14) ExoPlayerLib/2.11.7")
        lines.append(ch["url"])
        lines.append("")

    content = "\n".join(lines)
    os.makedirs(os.path.dirname(OUTPUT_M3U), exist_ok=True)
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ Generated {OUTPUT_M3U} with {len(SUNNXT_CHANNELS)} SunNXT channels.")

if __name__ == "__main__":
    generate_playlist()
