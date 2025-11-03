import random
import itertools
import json

# Load influencers and enemies
with open("board.json", "r") as f:
    board = json.load(f)
    influencers = {char["value"]: char for char in board["characters"]}

with open("player_building_sheet.json", "r") as f:
    all_buildings = json.load(f)["buildings"]

def get_new_player_state():
    return {
        "wood": 3, "stone": 3, "gold": 3, "armies": 0, "vp": 0, "plus2": 0,
        "buildings": [], "combat_log": [], "bonus_die": False, "kings_envoy": False,
        "type": "human", "name": "Player"
    }

players = [
]  # Each entry will be a dict with type ("human" or "bot") and their own player stats

# Load all enemies once at start
with open("bad_guy_cards.json", "r") as f:
    all_enemies = json.load(f)


# Emojis for resources
resource_emojis = {"wood": "🟫", "stone": "🔘", "gold": "🟡"}


def show_resources(p):
    print(f"\n{p['name']}'s current resources:")
    for key in ["wood", "stone", "gold", "armies", "vp", "plus2"]:
        label = "+2 Tokens" if key == "plus2" else key.capitalize()
        emoji = resource_emojis.get(key, "")
        print(f"  {label}: {p[key]} {emoji}")
    print()


def roll_dice(for_player):
    num_dice = 3 + (1 if for_player.get("bonus_die", False) else 0)
    return [random.randint(1, 6) for _ in range(num_dice)]


def setup_players():
    global players, auto_play
    print("\n🎲 Welcome to Kingsburg Console Edition!")
    user_input = input(
        "Press Enter to begin, type 'auto play' for a bot match, or type like '1 bot, 1 human' to add players: "
    ).strip().lower()

    if user_input == "auto play":
        print("Starting a 2-bot auto play game.")
        auto_play = True
        for i in range(2):
            p = get_new_player_state()
            p["type"] = "bot"
            p["name"] = f"Bot {i+1}"
            players.append(p)
        return

    if not user_input:
        print("Starting with 1 human player.")
        p = get_new_player_state()
        p["name"] = "Player 1"
        players.append(p)
        return

    # Parse input
    tokens = user_input.replace(",", "").split()
    i = 0
    while i < len(tokens):
        try:
            count = int(tokens[i])
            role = tokens[i + 1]
            if role in ["bot", "human"]:
                for n in range(count):
                    p = get_new_player_state()
                    p["type"] = role
                    p["name"] = f"{role.capitalize()} {len(players)+1}"
                    players.append(p)
                i += 2
            else:
                print(f"Unknown role '{role}'. Ignoring.")
                i += 1
        except (IndexError, ValueError):
            print("Couldn't understand part of the input. Ignoring.")
            break

    if not players:
        print("No valid players found. Defaulting to 1 human player.")
        p = get_new_player_state()
        p["name"] = "Player 1"
        players.append(p)


def get_possible_sums(dice):
    sums = {}
    for i in range(1, len(dice) + 1):
        for combo in itertools.combinations(range(len(dice)), i):
            dice_vals = tuple(dice[i] for i in combo)
            dice_sum = sum(dice_vals)
            if dice_sum not in sums:
                sums[dice_sum] = []
            sums[dice_sum].append(combo)
    return sums


def display_influencer_options(possible_sums, used_indices):
    print("\nAvailable influencer options:")
    shown = set()
    for val, combos in possible_sums.items():
        if val in influencers:
            for combo in combos:
                if all(i not in used_indices for i in combo):
                    if val not in shown:
                        print(
                            f"{val}: {influencers[val]['name']} - {influencers[val]['benefit']}"
                        )
                        shown.add(val)
                        print()
    if not shown:
        print("No valid influencer options left.")
        print()


def apply_actions(p, actions):
    for action in actions:
        typ = action["type"]
        resource = action.get("resource")

        if typ == "gain":
            p[resource] += action["amount"]
            print(f"Gained {action['amount']} {resource}.")
        elif typ == "lose":
            p[resource] = max(0, p[resource] - action["amount"])
            print(f"Lost {action['amount']} {resource}.")
        elif typ == "choose":
            handle_choose_action(p, {**action, "resource": resource})
        elif typ == "trade":
            handle_trade_action(p, action)
        elif typ == "peek":
            print("You peeked at the top enemy card! (feature coming soon)")
        else:
            print(f"Unknown action type: {typ}")


def choose_influencer(possible_sums, dice, used_indices):
    global current_player

    all_combos = {}  # Map from influencer value → dice combo
    for val, combos in possible_sums.items():
        if val in influencers:
            for combo in combos:
                if all(i not in used_indices for i in combo):
                    all_combos[val] = combo
                    break

    if not all_combos:
        print("No valid influencer options remaining.\n")
        return False

    while True:
        try:
            print("\nAvailable influencer options:")
            available_options = []
            for val in sorted(all_combos):
                already_claimed = influencer_owners.get(val)
                if already_claimed and already_claimed != current_player[
                        "name"] and not current_player.get(
                            "kings_envoy", False):
                    continue  # Skip showing blocked advisors
                available_options.append(val)
                print(
                    f"  {val}: {influencers[val]['name']} - {influencers[val]['benefit']}"
                )
            print()

            if current_player["type"] == "bot":
                choice = random.choice(available_options)
                print(
                    f"🤖 {current_player['name']} chooses influencer {choice}")
                raw = str(choice)
            else:
                raw = input(
                    "\nType the number of the influencer you want to use (e.g., '10+2', or '0' to skip): "
                ).strip().lower()

            if raw == "0":
                return False

            used_plus_two = False
            if "+2" in raw:
                if current_player.get("plus2", 0) <= 0:
                    print("❌ You don't have any +2 tokens.")
                    continue
                base = raw.replace("+2", "").strip()
                choice = int(base)
                actual_value = choice + 2
                used_plus_two = True
            else:
                choice = int(raw)
                actual_value = choice

            if actual_value not in influencers:
                print("❌ Invalid choice. No such influencer.")
                continue

            if influencer_owners.get(actual_value) and influencer_owners[
                    actual_value] != current_player["name"]:
                if not current_player.get("kings_envoy", False):
                    print(
                        f"❌ {actual_value} is already claimed by {influencer_owners[actual_value]}. You can't influence it."
                    )
                    continue
                else:
                    print(
                        f"👑 Using King's Envoy to influence an occupied advisor!"
                    )

            if not used_plus_two and actual_value not in all_combos:
                print(
                    "❌ You can't reach that influencer with your remaining dice."
                )
                continue

            influencer = influencers[actual_value]
            print(f"\nYou chose {influencer['name']} ({actual_value})!")
            print(f"Benefit: {influencer['benefit']}\n")

            if used_plus_two:
                current_player["plus2"] -= 1
                print("Used one +2 token.\n")

            apply_actions(current_player, influencer.get("actions", []))

            if not used_plus_two:
                used_indices.update(all_combos[actual_value])

            influencer_owners[actual_value] = current_player["name"]

            return True

        except ValueError:
            print(
                "❌ Invalid input. Please enter a number like '10' or '12+2'.")


def play_season(season_name):
    print(f"\n=== {season_name.upper()} ===")
    global influencer_owners
    influencer_owners = {}
    global current_player
    current_player = players[0]  # Set player manually for now

    if season_name != "Winter":
        apply_seasonal_bonuses(season_name)
        if season_name in ["Spring", "Summer", "Fall"]:
            award_kings_envoy()
        show_resources()
        if not auto_play:
            input("Press Enter to roll your dice: ")
        current_player = players[0]  # or whichever player should go first
        dice = roll_dice(current_player)
        used_indices = set()
        print(f"\nYou rolled: {dice}")

        possible_sums = get_possible_sums(dice)

        while len(used_indices) < 3:
            display_influencer_options(possible_sums, used_indices)
            if not choose_influencer(possible_sums, dice, used_indices):
                break

        # 💥 Add this line here
        build_phase()

    else:
        print("\n--- Winter Combat ---")
        return True  # trigger winter handling


def assign_bonus_dice():
    if len(players) <= 1:
        return  # No bonus needed for solo play

    min_vp = min(player["vp"] for player in players)

    for player in players:
        if player["vp"] == min_vp:
            player["bonus_die"] = True
            print(f"🎲 {player['name']} will get a bonus die next year!")
        else:
            player["bonus_die"] = False


def simulate_real_mini_game(players, all_buildings, influencers, log_file):
    global current_player, influencer_owners

    # Setup players cleanly
    for p in players:
        p["wood"] = random.randint(1, 5)
        p["stone"] = random.randint(1, 5)
        p["gold"] = random.randint(1, 5)
        p["vp"] = random.randint(0, 2)
        p["plus2"] = random.randint(0, 1)
        p["armies"] = random.randint(0, 3)
        p["buildings"] = []
        p["kings_envoy"] = False
        p["combat_log"] = []
        log_file.write(
            f"NEW GAME for {p['name']} -- {p['wood']}W/{p['stone']}S/{p['gold']}G, {p['vp']} VP, {p['armies']} armies.\n"
        )

    # Play 2 seasons: Spring, Summer
    for season in ["Spring", "Summer"]:
        log_file.write(f"\n== {season.upper()} ==\n")
        influencer_owners = {}

        for current_player in players:
            # Seasonal bonuses
            apply_seasonal_bonuses(season)

            # Roll dice
            dice = roll_dice(current_player)
            log_file.write(f"{current_player['name']} rolled {dice}\n")
            # Take snapshot BEFORE influencing
            before_wood = current_player["wood"]
            before_stone = current_player["stone"]
            before_gold = current_player["gold"]
            before_vp = current_player["vp"]

            used_indices = set()

            possible_sums = get_possible_sums(dice)

            # Influencer picks until dice exhausted
            while len(used_indices) < len(dice):
                display_influencer_options(possible_sums, used_indices)
                success = choose_influencer(possible_sums, dice, used_indices)
                if not success:
                    break

        # Building phase after all players' dice done
        for current_player in players:
            build_phase()

    # Handle Winter Combat
    log_file.write("\n== WINTER ==\n")
    for current_player in players:
        handle_winter(1)  # We'll just pass dummy round 1 for now

    log_file.write("\nFinal State:\n")
    for p in players:
        log_file.write(
            f"{p['name']}: {p['wood']}W/{p['stone']}S/{p['gold']}G, {p['vp']} VP, Buildings: {p.get('buildings',[])}\n"
        )
    log_file.write("\n" + "=" * 40 + "\n\n")


def run_random_stress_test(players, all_buildings, influencers):
    if len(players) == 2:
        print("\n⏩ Skipping stress test (two-player game detected).")
        return

    print("\n🧪 Running REAL Kingsburg mini-game stress test (100 games)...")
    log_path = "stress_test_log.txt"
    with open(log_path, "w") as log_file:
        try:
            for i in range(1, 101):
                simulate_real_mini_game(players, all_buildings, influencers,
                                        log_file)
                if i % 10 == 0:
                    print(f"  - {i} games simulated...")
        except Exception as e:
            log_file.write(
                f"\n❌ Error during simulation at game {i}: {e}\n")
            print(f"❌ Error during simulation at game {i}: {e}")
            return

    print(
        f"\n✅ REAL Kingsburg stress test completed successfully!\n📄 Log saved to {log_path}\n"
    )


def main():
    setup_players()
    run_random_stress_test(players, all_buildings, influencers)
    for round_num in range(1, 6):
        print(f"\n======= ROUND {round_num} =======")
        for season in ["Spring", "Summer", "Fall", "Winter"]:
            is_winter = play_season(season)
            if is_winter:
                handle_winter(round_num)
                assign_bonus_dice()


auto_play = False


def has_crane():
    for b in all_buildings:
        if b["level"] in current_player["buildings"]:
            for effect in b.get("effects", []):
                if effect["type"] == "unlock_rows" and "rows" in effect:
                    if 3 in effect["rows"] or 4 in effect["rows"]:
                        return True
    return False


def apply_enemy_reward(p, reward_str):
    if "gold" in reward_str:
        amount = int(reward_str.split("+")[1].split()[0])
        p["gold"] += amount
        print(f"Gained {amount} gold.")
    elif "victory point" in reward_str:
        amount = int(reward_str.split("+")[1].split()[0])
        p["vp"] += amount
        print(f"Gained {amount} victory point(s).")
    elif "resource of your choice" in reward_str:
        amount = int(reward_str.split("+")[1].split()[0])
        for _ in range(amount):
            choice = input(
                "Choose a resource to gain (wood/stone/gold): ").lower()
            if choice in p:
                p[choice] += 1
                print(f"Gained 1 {choice}.")
    elif "resources of your choice" in reward_str:
        amount = int(reward_str.split("+")[1].split()[0])
        for _ in range(amount):
            choice = input(
                "Choose a resource to gain (wood/stone/gold): ").lower()
            if choice in p:
                p[choice] += 1
                print(f"Gained 1 {choice}.")
    elif "defense" in reward_str:
        amount = int(reward_str.split("+")[1].split()[0])
        p["armies"] += amount
        print(f"Gained {amount} defense (armies).")
    print()


def build_phase():
    print("\n🏗 BUILDING PHASE")
    print("Your current buildings:", ", ".join(player["buildings"]) or "None")
    print()

    if current_player["type"] == "bot":
        if affordable:
            building = random.choice(affordable)
            for res, amt in building["cost"].items():
                current_player[res] -= amt
            current_player["buildings"].append(building["level"])
            print(f"🤖 {current_player['name']} built {building['name']} ({building['level']})!\n")
            apply_building_effects(building.get("effects", []))
        else:
            print(f"🤖 {current_player['name']} cannot afford any building.\n")
        return  # Bot finishes building phase immediately


    # Filter valid buildings
    buildable = []
    for b in all_buildings:
        level = b["level"]
        row, col = map(int, level.split("."))

        # Skip if already built
        if level in player["buildings"]:
            continue

        # Must have the previous building in the row (unless it's the first one)
        if col > 1 and f"{row}.{col-1}" not in player["buildings"]:
            continue

        # For rows 3 and 4: require row 1 and 2 unless you have Crane
        if row in [3, 4] and not has_crane():
            if not any(b.startswith("1.")
                       for b in player["buildings"]) or not any(
                           b.startswith("2.") for b in player["buildings"]):
                continue

        # Check if affordable
        cost = b["cost"]
        if (player["wood"] >= cost["wood"] and player["stone"] >= cost["stone"]
                and player["gold"] >= cost["gold"]):
            buildable.append(b)

    if not buildable:
        print("You can't build anything this season.")
        return

    print("\nYou can build:")
    for i, b in enumerate(buildable, 1):
        c = b["cost"]
        print(
            f"{i}: {b['name']} ({b['level']}) - Cost: {c['wood']}W/{c['stone']}S/{c['gold']}G - {b['benefit']}"
        )

    try:
        choice = input(
            "Type the number of the building you want to construct (or press Enter to skip): "
        ).strip()
        if not choice:
            return
        index = int(choice) - 1
        if 0 <= index < len(buildable):
            b = buildable[index]
            level = b["level"]
            cost = b["cost"]
            player["wood"] -= cost["wood"]
            player["stone"] -= cost["stone"]
            player["gold"] -= cost["gold"]
            player["buildings"].append(level)
            print(f"✅ You built the {b['name']}! ({level})")
            print(f"🏆 Benefit: {b['benefit']}")
            apply_building_effects(b.get("effects", []))
        else:
            print("Invalid choice.")
        print()
    except ValueError:
        print("Invalid input.")


def get_building_defense_bonus(enemy_name):
    total = 0
    enemy_name = enemy_name.lower()

    for b in all_buildings:
        if b["level"] in player["buildings"]:
            for effect in b.get("effects", []):
                if effect["type"] != "gain":
                    continue

                res = effect["resource"]
                amt = effect["amount"]

                if res == "defense":
                    total += amt
                elif res == "demon_defense" and "demon" in enemy_name:
                    total += amt
                elif res == "zombie_defense" and "zombie" in enemy_name:
                    total += amt
                elif res == "goblin_defense" and "goblin" in enemy_name:
                    total += amt

    return total


def apply_building_effects(effects):
    for effect in effects:
        typ = effect["type"]

        if typ == "gain":
            res = effect["resource"]
            amt = effect["amount"]
            if res == "any":
                for i in range(amt):
                    choice = input(
                        f"Choose a resource to gain ({i+1} of {amt}): wood/stone/gold: "
                    ).lower()
                    if choice in ["wood", "stone", "gold"]:
                        current_player[choice] += 1
                        print(f"Gained 1 {choice}.")
            else:
                player[res] = player.get(res, 0) + amt
                print(f"Gained {amt} {res}.")

        elif typ == "season_bonus":
            print(
                f"(Note: +{effect['amount']} {effect['resource']} bonus in {effect['season']})"
            )

        elif typ == "influence_bonus":
            print(f"(Note: +{effect['amount']} influence per season)")

        elif typ == "tie_breaker":
            print("You now win ties in combat.")

        elif typ == "extra_advisor":
            print(f"You may influence {effect['amount']} extra advisor(s).")

        elif typ == "bonus_vp_per_win":
            print(f"(Note: +{effect['amount']} VP per combat win)")

        elif typ == "unlock_rows":
            print(f"(Unlocked building rows: {effect['rows']})")

        else:
            print(f"⚠️ Unknown effect type: {typ}")

        print()  # Add line break for readability


def apply_loss_penalty(p, loss_str):
    print("\n🩸 Applying penalty...")

    tokens = [t.strip().lower() for t in loss_str.replace(',', '').split()]
    i = 0

    while i < len(tokens):
        if tokens[i].startswith('-'):
            try:
                amount = int(tokens[i][1:])
            except ValueError:
                print(f"⚠️ Couldn't parse number from: {tokens[i]}")
                i += 1
                continue

            if i + 1 >= len(tokens):
                break

            kind = tokens[i + 1]

            if kind in [
                    "vp", "victory", "victorypoint", "victorypoints", "point",
                    "points"
            ]:
                p["vp"] = max(0, p["vp"] - amount)
                print(f"❌ Lost {amount} VP.")
            elif kind == "resource" or kind == "resources":
                # Deduct any resources randomly
                pool = []
                for r in ["wood", "stone", "gold"]:
                    pool += [r] * p[r]
                if not pool:
                    print("No resources to lose.")
                else:
                    for _ in range(amount):
                        if not pool:
                            break
                        chosen = random.choice(pool)
                        p[chosen] -= 1
                        pool = [
                            r for r in pool if r != chosen or p[r] > 0
                        ]
                        print(f"❌ Lost 1 {chosen}.")
            elif kind in ["wood", "stone", "gold"]:
                p[kind] = max(0, p[kind] - amount)
                print(f"❌ Lost {amount} {kind}.")
            elif kind == "building":
                print("❌ Lost 1 building. (Feature not implemented yet.)")
            else:
                print(f"⚠️ Unknown penalty type: {kind}")

            i += 2
        else:
            i += 1


def handle_choose_action(p, action):
    res = action["resource"]
    amount = action["amount"]

    if isinstance(res, list) and all(isinstance(r, list) for r in res):
        # This is a list of resource combinations to choose from
        print("\nChoose one of the following resource combinations:")
        for i, combo in enumerate(res, 1):
            print(f"{i}: " + " + ".join(combo))
        while True:
            try:
                choice = int(input("Your choice: "))
                if 1 <= choice <= len(res):
                    for r in res[choice - 1]:
                        p[r] += 1
                        print(f"Gained 1 {r}.")
                    break
                else:
                    print("Invalid choice.")
            except ValueError:
                print("Please enter a number.")
    elif res == "any":
        for i in range(amount):
            choice = input(
                f"Choose a resource to gain ({i+1} of {amount}): wood/stone/gold: "
            ).lower()
            if choice in ["wood", "stone", "gold"]:
                p[choice] += 1
                print(f"Gained 1 {choice}.")
            else:
                print("Invalid resource.")
    elif isinstance(res, list):
        print("Choose one of the following options:")
        for i, option in enumerate(res, 1):
            print(f"{i}: {option}")
        while True:
            try:
                choice = int(input("Your choice: "))
                if 1 <= choice <= len(res):
                    selected = res[choice - 1]
                    p[selected] += amount
                    print(f"Gained {amount} {selected}.")
                    break
                else:
                    print("Invalid choice.")
            except ValueError:
                print("Please enter a number.")


def handle_trade_action(p, action):
    print("\n--- Trade Action ---")
    resources = ["wood", "stone", "gold"]
    choices = []

    for res in resources:
        if p[res] >= 1:
            give = res
            get = [r for r in resources if r != res]
            choices.append((give, get))

    if not choices:
        print("You don't have any resources to trade.")
        return

    for i, (give, get) in enumerate(choices, 1):
        print(f"{i}: Give 1 {give} → Gain 1 {get[0]} and 1 {get[1]}")

    while True:
        try:
            choice = int(input("Choose your trade option: "))
            if 1 <= choice <= len(choices):
                give, get = choices[choice - 1]
                p[give] -= 1
                p[get[0]] += 1
                p[get[1]] += 1
                print(f"Gave 1 {give}, gained 1 {get[0]} and 1 {get[1]}.")
                break
            else:
                print("Invalid choice.")
        except ValueError:
            print("Please enter a number.")


def get_random_enemy_for_level(level):
    options = [e for e in all_enemies if e["level"] == level]
    return random.choice(options) if options else None


def handle_winter(round_number):
    level = round_number  # level matches the round
    enemy = get_random_enemy_for_level(level)

    if not enemy:
        print("No enemy found for this round.")
        return

    print(f"\n⚔️  Enemy: {enemy['name']}")
    print(f"   Strength: {enemy['strength']}")
    print(f"   Reward if you win: {enemy['reward']}")
    print(f"   Penalty if you lose: {enemy['loss']}")

    # Roll the King's die
    king_die = random.randint(1, 6)
    building_defense = get_building_defense_bonus(enemy["name"])
    total_power = player["armies"] + king_die + building_defense

    print(f"\n🛡️  Your Armies: {player['armies']}")
    print(f"👑 King's Die: {king_die}")
    print(f"🏰 Building Defense Bonus: {building_defense}")
    print(f"⚔️  Total Power: {total_power}")

    enemy_strength = enemy["strength"]
    tie_breaker = has_tie_breaker()
    if tie_breaker:
        print("🏰 You have a tie-breaker building!")

    if total_power > enemy_strength or (total_power == enemy_strength
                                        and tie_breaker):

        print("✅ You defeated the enemy!")
        apply_enemy_reward(enemy["reward"])
        bonus_vp = get_bonus_vp_per_win()
        if bonus_vp > 0:
            player["vp"] += bonus_vp
            print(f"🏆 Bonus: Gained {bonus_vp} VP from your buildings!")
            print()
        player["combat_log"].append({
            "round": round_number,
            "enemy": enemy["name"],
            "result": "win"
        })
    else:
        print("❌ You lost the battle!")
        player["combat_log"].append({
            "round": round_number,
            "enemy": enemy["name"],
            "result": "loss"
        })
        apply_loss_penalty(enemy["loss"])

    if (round_number == 5):
        show_final_summary()


def show_final_summary():
    print("\n🎉 GAME OVER — Final Summary 🎉")
    print("-" * 40)

    print(f"\n🏆 Total Victory Points: {player['vp']}")
    print(
        f"🎯 Resources Left: Wood: {player['wood']}, Stone: {player['stone']}, Gold: {player['gold']}"
    )
    print(f"🎲 +2 Tokens Left: {player['plus2']}")
    print()

    print("🏰 Buildings Constructed:")
    if player["buildings"]:
        for b in player["buildings"]:
            name = next(build["name"] for build in all_buildings
                        if build["level"] == b)
            print(f"  - {b}: {name}")
    else:
        print("  None")

    print()

    print("⚔️  Combat Log:")
    if player.get("combat_log"):
        for entry in player["combat_log"]:
            result = "✅ WIN" if entry["result"] == "win" else "❌ LOSS"
            print(f"  Round {entry['round']}: {entry['enemy']} - {result}")
    else:
        print("  No combat recorded.")

    print("\nThanks for playing Kingsburg Console Edition!")
    print("-" * 40)
    print()


def apply_seasonal_bonuses(season_name):
    print(f"\n🌞 Checking seasonal bonuses for {season_name}...")
    triggered = False

    for b in all_buildings:
        if b["level"] in player["buildings"]:
            for effect in b.get("effects", []):
                if effect["type"] == "season_bonus" and effect["season"].lower(
                ) == season_name.lower():
                    amt = effect["amount"]
                    res = effect["resource"]

                    if res == "any":
                        for i in range(amt):
                            choice = input(
                                f"Choose a resource to gain ({i+1} of {amt}): wood/stone/gold: "
                            ).lower()
                            if choice in ["wood", "stone", "gold"]:
                                player[choice] += 1
                                print(f"Gained 1 {choice}.")
                    else:
                        player[res] += amt
                        print(f"Gained {amt} {res} from seasonal bonus.")

                    triggered = True
                    print()

    if not triggered:
        print("No seasonal bonuses this round.\n")


def has_tie_breaker():
    for b in all_buildings:
        if b["level"] in player["buildings"]:
            for effect in b.get("effects", []):
                if effect["type"] == "tie_breaker":
                    return True
    return False


def get_bonus_vp_per_win():
    total = 0
    for b in all_buildings:
        if b["level"] in player["buildings"]:
            for effect in b.get("effects", []):
                if effect["type"] == "bonus_vp_per_win":
                    total += effect["amount"]
    return total


def award_kings_envoy():
    if len(players) <= 1:
        return  # No envoy needed for solo

    fewest_buildings = min(len(p.get("buildings", [])) for p in players)

    tied = [
        p for p in players if len(p.get("buildings", [])) == fewest_buildings
    ]

    if len(tied) == 1:
        winner = tied[0]
    else:
        # Tiebreaker: fewest goods
        winner = min(tied,
                     key=lambda p: p.get("wood", 0) + p.get("stone", 0) + p.
                     get("gold", 0))

    for p in players:
        p["kings_envoy"] = False

    winner["kings_envoy"] = True
    print(f"👑 {winner['name']} has been awarded the King's Envoy!\n")
