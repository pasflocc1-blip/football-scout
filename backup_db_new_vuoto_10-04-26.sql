--
-- PostgreSQL database dump
--

\restrict Dijy8hNaQiBtDfkELbqkhac8vXBqjHeE3K4rBwogNW00sQpmERS5PnTxWnMXTDN

-- Dumped from database version 15.17
-- Dumped by pg_dump version 15.17

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: traittype; Type: TYPE; Schema: public; Owner: football
--

CREATE TYPE public.traittype AS ENUM (
    'positive',
    'negative'
);


ALTER TYPE public.traittype OWNER TO football;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: football
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO football;

--
-- Name: clubs; Type: TABLE; Schema: public; Owner: football
--

CREATE TABLE public.clubs (
    id integer NOT NULL,
    name character varying,
    league_key character varying,
    country character varying
);


ALTER TABLE public.clubs OWNER TO football;

--
-- Name: clubs_id_seq; Type: SEQUENCE; Schema: public; Owner: football
--

CREATE SEQUENCE public.clubs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.clubs_id_seq OWNER TO football;

--
-- Name: clubs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: football
--

ALTER SEQUENCE public.clubs_id_seq OWNED BY public.clubs.id;


--
-- Name: my_players; Type: TABLE; Schema: public; Owner: football
--

CREATE TABLE public.my_players (
    id integer NOT NULL,
    team_id integer,
    name character varying(100) NOT NULL,
    "position" character varying(20),
    age integer,
    preferred_foot character varying(10),
    rating double precision,
    season character varying(20)
);


ALTER TABLE public.my_players OWNER TO football;

--
-- Name: my_players_id_seq; Type: SEQUENCE; Schema: public; Owner: football
--

CREATE SEQUENCE public.my_players_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.my_players_id_seq OWNER TO football;

--
-- Name: my_players_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: football
--

ALTER SEQUENCE public.my_players_id_seq OWNED BY public.my_players.id;


--
-- Name: my_team; Type: TABLE; Schema: public; Owner: football
--

CREATE TABLE public.my_team (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    formation character varying(20),
    league character varying(100),
    season character varying(20),
    coach character varying(100),
    budget double precision,
    notes text,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


ALTER TABLE public.my_team OWNER TO football;

--
-- Name: my_team_id_seq; Type: SEQUENCE; Schema: public; Owner: football
--

CREATE SEQUENCE public.my_team_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.my_team_id_seq OWNER TO football;

--
-- Name: my_team_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: football
--

ALTER SEQUENCE public.my_team_id_seq OWNED BY public.my_team.id;


--
-- Name: player_career; Type: TABLE; Schema: public; Owner: football
--

CREATE TABLE public.player_career (
    id integer NOT NULL,
    player_id integer NOT NULL,
    from_team character varying(100),
    to_team character varying(100),
    transfer_date timestamp without time zone,
    fee double precision,
    transfer_type character varying(30),
    season character varying(10),
    source character varying(20),
    fetched_at timestamp without time zone
);


ALTER TABLE public.player_career OWNER TO football;

--
-- Name: player_career_id_seq; Type: SEQUENCE; Schema: public; Owner: football
--

CREATE SEQUENCE public.player_career_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.player_career_id_seq OWNER TO football;

--
-- Name: player_career_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: football
--

ALTER SEQUENCE public.player_career_id_seq OWNED BY public.player_career.id;


--
-- Name: player_fbref_match_logs; Type: TABLE; Schema: public; Owner: football
--

CREATE TABLE public.player_fbref_match_logs (
    id integer NOT NULL,
    player_id integer NOT NULL,
    season character varying(10),
    date character varying(20),
    dayofweek character varying(10),
    comp character varying(80),
    round character varying(40),
    venue character varying(10),
    result character varying(15),
    team character varying(80),
    opponent character varying(80),
    game_started character varying(5),
    "position" character varying(10),
    minutes integer,
    goals integer,
    assists integer,
    pens_made integer,
    pens_att integer,
    shots integer,
    shots_on_target integer,
    yellow_card integer,
    red_card integer,
    fouls_committed integer,
    fouls_drawn integer,
    offsides integer,
    crosses integer,
    tackles_won integer,
    interceptions integer,
    own_goals integer,
    pens_won character varying(5),
    pens_conceded character varying(5),
    fetched_at timestamp without time zone
);


ALTER TABLE public.player_fbref_match_logs OWNER TO football;

--
-- Name: player_fbref_match_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: football
--

CREATE SEQUENCE public.player_fbref_match_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.player_fbref_match_logs_id_seq OWNER TO football;

--
-- Name: player_fbref_match_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: football
--

ALTER SEQUENCE public.player_fbref_match_logs_id_seq OWNED BY public.player_fbref_match_logs.id;


--
-- Name: player_fbref_stats; Type: TABLE; Schema: public; Owner: football
--

CREATE TABLE public.player_fbref_stats (
    id integer NOT NULL,
    player_id integer NOT NULL,
    season character varying(10) NOT NULL,
    league character varying(80) NOT NULL,
    appearances integer,
    starts integer,
    minutes integer,
    goals integer,
    assists integer,
    goals_pens integer,
    pens_made integer,
    pens_att integer,
    yellow_cards integer,
    red_cards integer,
    xg double precision,
    npxg double precision,
    xa double precision,
    npxg_xa double precision,
    goals_per90 double precision,
    assists_per90 double precision,
    xg_per90 double precision,
    xa_per90 double precision,
    npxg_per90 double precision,
    shots integer,
    shots_on_target integer,
    shots_on_target_pct double precision,
    shots_per90 double precision,
    sot_per90 double precision,
    goals_per_shot double precision,
    goals_per_sot double precision,
    avg_shot_distance double precision,
    npxg_per_shot double precision,
    xg_net double precision,
    npxg_net double precision,
    passes_completed integer,
    passes_attempted integer,
    pass_completion_pct double precision,
    passes_total_dist double precision,
    passes_prog_dist double precision,
    passes_short_pct double precision,
    passes_medium_pct double precision,
    passes_long_completed integer,
    passes_long_attempted integer,
    passes_long_pct double precision,
    key_passes integer,
    passes_final_third integer,
    passes_penalty_area integer,
    crosses_penalty_area integer,
    progressive_passes integer,
    xa_pass double precision,
    sca integer,
    sca_per90 double precision,
    sca_pass_live integer,
    sca_pass_dead integer,
    sca_take_on integer,
    sca_shot integer,
    gca integer,
    gca_per90 double precision,
    gca_pass_live integer,
    gca_take_on integer,
    tackles integer,
    tackles_won integer,
    tackles_def_3rd integer,
    tackles_mid_3rd integer,
    tackles_att_3rd integer,
    challenge_tackles integer,
    challenges integer,
    challenge_tackles_pct double precision,
    blocks integer,
    blocked_shots integer,
    blocked_passes integer,
    interceptions integer,
    tkl_int integer,
    clearances integer,
    errors integer,
    touches integer,
    touches_def_pen integer,
    touches_def_3rd integer,
    touches_mid_3rd integer,
    touches_att_3rd integer,
    touches_att_pen integer,
    take_ons_att integer,
    take_ons_succ integer,
    take_ons_succ_pct double precision,
    take_ons_tackled integer,
    carries integer,
    carries_prog_dist double precision,
    progressive_carries integer,
    carries_final_third integer,
    carries_penalty_area integer,
    miscontrols integer,
    dispossessed integer,
    progressive_passes_received integer,
    fouls_committed integer,
    fouls_drawn integer,
    offsides integer,
    crosses integer,
    pens_won integer,
    pens_conceded integer,
    own_goals integer,
    ball_recoveries integer,
    aerials_won integer,
    aerials_lost integer,
    aerials_won_pct double precision,
    fbref_player_id character varying(20),
    fetched_at timestamp without time zone,
    updated_at timestamp without time zone
);


ALTER TABLE public.player_fbref_stats OWNER TO football;

--
-- Name: player_fbref_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: football
--

CREATE SEQUENCE public.player_fbref_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.player_fbref_stats_id_seq OWNER TO football;

--
-- Name: player_fbref_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: football
--

ALTER SEQUENCE public.player_fbref_stats_id_seq OWNED BY public.player_fbref_stats.id;


--
-- Name: player_heatmap; Type: TABLE; Schema: public; Owner: football
--

CREATE TABLE public.player_heatmap (
    id integer NOT NULL,
    player_id integer NOT NULL,
    season character varying(10) NOT NULL,
    league character varying(50) NOT NULL,
    points json,
    point_count integer,
    position_played character varying(20),
    source character varying(20),
    fetched_at timestamp without time zone
);


ALTER TABLE public.player_heatmap OWNER TO football;

--
-- Name: player_heatmap_id_seq; Type: SEQUENCE; Schema: public; Owner: football
--

CREATE SEQUENCE public.player_heatmap_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.player_heatmap_id_seq OWNER TO football;

--
-- Name: player_heatmap_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: football
--

ALTER SEQUENCE public.player_heatmap_id_seq OWNED BY public.player_heatmap.id;


--
-- Name: player_matches; Type: TABLE; Schema: public; Owner: football
--

CREATE TABLE public.player_matches (
    id integer NOT NULL,
    player_id integer NOT NULL,
    event_id integer,
    date timestamp without time zone,
    season character varying(10),
    tournament character varying(100),
    home_team character varying(100),
    away_team character varying(100),
    home_score integer,
    away_score integer,
    rating double precision,
    minutes_played integer,
    goals integer,
    assists integer,
    yellow_card integer,
    red_card integer,
    source character varying(20),
    fetched_at timestamp without time zone
);


ALTER TABLE public.player_matches OWNER TO football;

--
-- Name: player_matches_id_seq; Type: SEQUENCE; Schema: public; Owner: football
--

CREATE SEQUENCE public.player_matches_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.player_matches_id_seq OWNER TO football;

--
-- Name: player_matches_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: football
--

ALTER SEQUENCE public.player_matches_id_seq OWNED BY public.player_matches.id;


--
-- Name: player_national_stats; Type: TABLE; Schema: public; Owner: football
--

CREATE TABLE public.player_national_stats (
    id integer NOT NULL,
    player_id integer NOT NULL,
    national_team character varying(100),
    season character varying(10),
    appearances integer,
    minutes integer,
    goals integer,
    assists integer,
    rating double precision,
    yellow_cards integer,
    red_cards integer,
    raw_data json,
    source character varying(20),
    fetched_at timestamp without time zone,
    updated_at timestamp without time zone
);


ALTER TABLE public.player_national_stats OWNER TO football;

--
-- Name: player_national_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: football
--

CREATE SEQUENCE public.player_national_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.player_national_stats_id_seq OWNER TO football;

--
-- Name: player_national_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: football
--

ALTER SEQUENCE public.player_national_stats_id_seq OWNED BY public.player_national_stats.id;


--
-- Name: player_scouting_index; Type: TABLE; Schema: public; Owner: football
--

CREATE TABLE public.player_scouting_index (
    id integer NOT NULL,
    player_id integer NOT NULL,
    season character varying(10) NOT NULL,
    position_group character varying(5),
    finishing_index double precision,
    creativity_index double precision,
    pressing_index double precision,
    carrying_index double precision,
    defending_index double precision,
    buildup_index double precision,
    overall_index double precision,
    finishing_pct double precision,
    creativity_pct double precision,
    pressing_pct double precision,
    carrying_pct double precision,
    defending_pct double precision,
    buildup_pct double precision,
    heading_score double precision,
    xg_per90 double precision,
    xa_per90 double precision,
    npxg_per90 double precision,
    sca_per90 double precision,
    gca_per90 double precision,
    progressive_carries_per90 double precision,
    progressive_passes_per90 double precision,
    tackles_won_per90 double precision,
    interceptions_per90 double precision,
    aerials_won_pct double precision,
    take_ons_succ_pct double precision,
    pass_completion_pct double precision,
    goals_per_shot double precision,
    ball_recoveries_per90 double precision,
    crosses_per90 double precision,
    sources_used json,
    data_confidence double precision,
    minutes_sample integer,
    computed_at timestamp without time zone,
    updated_at timestamp without time zone
);


ALTER TABLE public.player_scouting_index OWNER TO football;

--
-- Name: player_scouting_index_id_seq; Type: SEQUENCE; Schema: public; Owner: football
--

CREATE SEQUENCE public.player_scouting_index_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.player_scouting_index_id_seq OWNER TO football;

--
-- Name: player_scouting_index_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: football
--

ALTER SEQUENCE public.player_scouting_index_id_seq OWNED BY public.player_scouting_index.id;


--
-- Name: player_season_stats; Type: TABLE; Schema: public; Owner: football
--

CREATE TABLE public.player_season_stats (
    id integer NOT NULL,
    player_id integer NOT NULL,
    season character varying(10) NOT NULL,
    league character varying(50) NOT NULL,
    source character varying(30) NOT NULL,
    sofascore_rating double precision,
    appearances integer,
    matches_started integer,
    minutes_played integer,
    goals integer,
    assists integer,
    goals_assists_sum integer,
    shots_total integer,
    shots_on_target integer,
    shots_off_target integer,
    shots_inside_box integer,
    shots_outside_box integer,
    big_chances_created integer,
    big_chances_missed integer,
    goal_conversion_pct double precision,
    headed_goals integer,
    left_foot_goals integer,
    right_foot_goals integer,
    goals_inside_box integer,
    goals_outside_box integer,
    free_kick_goals integer,
    penalty_goals integer,
    penalty_taken integer,
    penalty_won integer,
    own_goals integer,
    xg double precision,
    xa double precision,
    xg_per90 double precision,
    xa_per90 double precision,
    npxg_per90 double precision,
    xgchain_per90 double precision,
    xgbuildup_per90 double precision,
    accurate_passes integer,
    inaccurate_passes integer,
    total_passes integer,
    pass_accuracy_pct double precision,
    accurate_own_half_passes integer,
    accurate_opp_half_passes integer,
    accurate_final_third_passes integer,
    accurate_long_balls integer,
    long_ball_accuracy_pct double precision,
    total_long_balls integer,
    accurate_crosses integer,
    cross_accuracy_pct double precision,
    total_crosses integer,
    key_passes integer,
    pass_to_assist integer,
    chipped_passes integer,
    progressive_passes integer,
    progressive_carries integer,
    progressive_passes_received integer,
    touches_att_pen integer,
    successful_dribbles integer,
    dribble_success_pct double precision,
    dribbled_past integer,
    dispossessed integer,
    ground_duels_won integer,
    ground_duels_won_pct double precision,
    aerial_duels_won integer,
    aerial_duels_lost integer,
    aerial_duels_won_pct double precision,
    total_duels_won integer,
    total_duels_won_pct double precision,
    total_contest integer,
    tackles integer,
    tackles_won integer,
    tackles_won_pct double precision,
    interceptions integer,
    clearances integer,
    blocked_shots integer,
    errors_led_to_goal integer,
    errors_led_to_shot integer,
    ball_recovery integer,
    possession_won_att_third integer,
    pressures integer,
    pressure_regains integer,
    touches integer,
    possession_lost integer,
    shot_from_set_piece integer,
    yellow_cards integer,
    yellow_red_cards integer,
    red_cards integer,
    fouls_committed integer,
    fouls_won integer,
    offsides integer,
    hit_woodwork integer,
    saves integer,
    goals_conceded integer,
    goals_conceded_inside_box integer,
    goals_conceded_outside_box integer,
    clean_sheets integer,
    penalty_saved integer,
    penalty_faced integer,
    high_claims integer,
    punches integer,
    runs_out integer,
    successful_runs_out integer,
    saved_shots_inside_box integer,
    saved_shots_outside_box integer,
    fanta_media double precision,
    fanta_media_mv double precision,
    fanta_gol integer,
    fanta_assist integer,
    fanta_ammonizioni integer,
    fanta_espulsioni integer,
    fanta_rigori_segnati integer,
    fanta_rigori_sbagliati integer,
    fanta_autogol integer,
    fanta_presenze integer,
    tournament_id integer,
    season_id integer,
    fetched_at timestamp without time zone,
    updated_at timestamp without time zone
);


ALTER TABLE public.player_season_stats OWNER TO football;

--
-- Name: player_season_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: football
--

CREATE SEQUENCE public.player_season_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.player_season_stats_id_seq OWNER TO football;

--
-- Name: player_season_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: football
--

ALTER SEQUENCE public.player_season_stats_id_seq OWNED BY public.player_season_stats.id;


--
-- Name: player_sofascore_stats; Type: TABLE; Schema: public; Owner: football
--

CREATE TABLE public.player_sofascore_stats (
    id integer NOT NULL,
    player_id integer NOT NULL,
    season character varying(10) NOT NULL,
    league character varying(80) NOT NULL,
    sofascore_rating double precision,
    appearances integer,
    matches_started integer,
    minutes_played integer,
    goals integer,
    assists integer,
    goals_assists_sum integer,
    shots_total integer,
    shots_on_target integer,
    shots_off_target integer,
    big_chances_created integer,
    big_chances_missed integer,
    goal_conversion_pct double precision,
    headed_goals integer,
    penalty_goals integer,
    penalty_won integer,
    xg double precision,
    xa double precision,
    xg_per90 double precision,
    xa_per90 double precision,
    accurate_passes integer,
    inaccurate_passes integer,
    total_passes integer,
    pass_accuracy_pct double precision,
    accurate_long_balls integer,
    long_ball_accuracy_pct double precision,
    total_long_balls integer,
    accurate_crosses integer,
    cross_accuracy_pct double precision,
    total_crosses integer,
    key_passes integer,
    accurate_own_half_passes integer,
    accurate_opp_half_passes integer,
    accurate_final_third_passes integer,
    successful_dribbles integer,
    dribble_attempts integer,
    dribble_success_pct double precision,
    dribbled_past integer,
    dispossessed integer,
    ground_duels_won integer,
    ground_duels_won_pct double precision,
    aerial_duels_won integer,
    aerial_duels_lost integer,
    aerial_duels_won_pct double precision,
    total_duels_won integer,
    total_duels_won_pct double precision,
    total_contest integer,
    tackles integer,
    tackles_won integer,
    tackles_won_pct double precision,
    interceptions integer,
    clearances integer,
    blocked_shots integer,
    errors_led_to_goal integer,
    errors_led_to_shot integer,
    ball_recovery integer,
    possession_won_att_third integer,
    touches integer,
    possession_lost integer,
    yellow_cards integer,
    yellow_red_cards integer,
    red_cards integer,
    fouls_committed integer,
    fouls_won integer,
    offsides integer,
    hit_woodwork integer,
    saves integer,
    goals_conceded integer,
    clean_sheets integer,
    penalty_saved integer,
    penalty_faced integer,
    high_claims integer,
    punches integer,
    tournament_id integer,
    season_id integer,
    season_club character varying(80),
    attributes_raw json,
    attributes_avg_raw json,
    fetched_at timestamp without time zone,
    updated_at timestamp without time zone
);


ALTER TABLE public.player_sofascore_stats OWNER TO football;

--
-- Name: player_sofascore_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: football
--

CREATE SEQUENCE public.player_sofascore_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.player_sofascore_stats_id_seq OWNER TO football;

--
-- Name: player_sofascore_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: football
--

ALTER SEQUENCE public.player_sofascore_stats_id_seq OWNED BY public.player_sofascore_stats.id;


--
-- Name: scouting_players; Type: TABLE; Schema: public; Owner: football
--

CREATE TABLE public.scouting_players (
    id integer NOT NULL,
    api_football_id integer,
    transfermarkt_id character varying(50),
    fbref_id character varying(50),
    understat_id character varying(20),
    sofascore_id character varying(20),
    name character varying(100) NOT NULL,
    birth_date date,
    "position" character varying(20),
    position_detail character varying(50),
    club character varying(100),
    club_id integer,
    nationality character varying(50),
    age integer,
    preferred_foot character varying(10),
    height integer,
    weight integer,
    jersey_number integer,
    gender character varying(5),
    market_value double precision,
    contract_until date,
    sofascore_rating double precision,
    last_updated_understat timestamp without time zone,
    last_updated_fbref timestamp without time zone,
    last_updated_api_football timestamp without time zone,
    last_updated_statsbomb timestamp without time zone,
    last_updated_sofascore timestamp without time zone,
    updated_at timestamp without time zone
);


ALTER TABLE public.scouting_players OWNER TO football;

--
-- Name: scouting_players_id_seq; Type: SEQUENCE; Schema: public; Owner: football
--

CREATE SEQUENCE public.scouting_players_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.scouting_players_id_seq OWNER TO football;

--
-- Name: scouting_players_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: football
--

ALTER SEQUENCE public.scouting_players_id_seq OWNED BY public.scouting_players.id;


--
-- Name: team_traits; Type: TABLE; Schema: public; Owner: football
--

CREATE TABLE public.team_traits (
    id integer NOT NULL,
    team_id integer NOT NULL,
    trait_type public.traittype NOT NULL,
    description text NOT NULL,
    priority integer
);


ALTER TABLE public.team_traits OWNER TO football;

--
-- Name: team_traits_id_seq; Type: SEQUENCE; Schema: public; Owner: football
--

CREATE SEQUENCE public.team_traits_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.team_traits_id_seq OWNER TO football;

--
-- Name: team_traits_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: football
--

ALTER SEQUENCE public.team_traits_id_seq OWNED BY public.team_traits.id;


--
-- Name: clubs id; Type: DEFAULT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.clubs ALTER COLUMN id SET DEFAULT nextval('public.clubs_id_seq'::regclass);


--
-- Name: my_players id; Type: DEFAULT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.my_players ALTER COLUMN id SET DEFAULT nextval('public.my_players_id_seq'::regclass);


--
-- Name: my_team id; Type: DEFAULT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.my_team ALTER COLUMN id SET DEFAULT nextval('public.my_team_id_seq'::regclass);


--
-- Name: player_career id; Type: DEFAULT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_career ALTER COLUMN id SET DEFAULT nextval('public.player_career_id_seq'::regclass);


--
-- Name: player_fbref_match_logs id; Type: DEFAULT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_fbref_match_logs ALTER COLUMN id SET DEFAULT nextval('public.player_fbref_match_logs_id_seq'::regclass);


--
-- Name: player_fbref_stats id; Type: DEFAULT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_fbref_stats ALTER COLUMN id SET DEFAULT nextval('public.player_fbref_stats_id_seq'::regclass);


--
-- Name: player_heatmap id; Type: DEFAULT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_heatmap ALTER COLUMN id SET DEFAULT nextval('public.player_heatmap_id_seq'::regclass);


--
-- Name: player_matches id; Type: DEFAULT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_matches ALTER COLUMN id SET DEFAULT nextval('public.player_matches_id_seq'::regclass);


--
-- Name: player_national_stats id; Type: DEFAULT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_national_stats ALTER COLUMN id SET DEFAULT nextval('public.player_national_stats_id_seq'::regclass);


--
-- Name: player_scouting_index id; Type: DEFAULT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_scouting_index ALTER COLUMN id SET DEFAULT nextval('public.player_scouting_index_id_seq'::regclass);


--
-- Name: player_season_stats id; Type: DEFAULT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_season_stats ALTER COLUMN id SET DEFAULT nextval('public.player_season_stats_id_seq'::regclass);


--
-- Name: player_sofascore_stats id; Type: DEFAULT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_sofascore_stats ALTER COLUMN id SET DEFAULT nextval('public.player_sofascore_stats_id_seq'::regclass);


--
-- Name: scouting_players id; Type: DEFAULT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.scouting_players ALTER COLUMN id SET DEFAULT nextval('public.scouting_players_id_seq'::regclass);


--
-- Name: team_traits id; Type: DEFAULT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.team_traits ALTER COLUMN id SET DEFAULT nextval('public.team_traits_id_seq'::regclass);


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: football
--

COPY public.alembic_version (version_num) FROM stdin;
76f54fd05e85
\.


--
-- Data for Name: clubs; Type: TABLE DATA; Schema: public; Owner: football
--

COPY public.clubs (id, name, league_key, country) FROM stdin;
\.


--
-- Data for Name: my_players; Type: TABLE DATA; Schema: public; Owner: football
--

COPY public.my_players (id, team_id, name, "position", age, preferred_foot, rating, season) FROM stdin;
\.


--
-- Data for Name: my_team; Type: TABLE DATA; Schema: public; Owner: football
--

COPY public.my_team (id, name, formation, league, season, coach, budget, notes, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: player_career; Type: TABLE DATA; Schema: public; Owner: football
--

COPY public.player_career (id, player_id, from_team, to_team, transfer_date, fee, transfer_type, season, source, fetched_at) FROM stdin;
\.


--
-- Data for Name: player_fbref_match_logs; Type: TABLE DATA; Schema: public; Owner: football
--

COPY public.player_fbref_match_logs (id, player_id, season, date, dayofweek, comp, round, venue, result, team, opponent, game_started, "position", minutes, goals, assists, pens_made, pens_att, shots, shots_on_target, yellow_card, red_card, fouls_committed, fouls_drawn, offsides, crosses, tackles_won, interceptions, own_goals, pens_won, pens_conceded, fetched_at) FROM stdin;
\.


--
-- Data for Name: player_fbref_stats; Type: TABLE DATA; Schema: public; Owner: football
--

COPY public.player_fbref_stats (id, player_id, season, league, appearances, starts, minutes, goals, assists, goals_pens, pens_made, pens_att, yellow_cards, red_cards, xg, npxg, xa, npxg_xa, goals_per90, assists_per90, xg_per90, xa_per90, npxg_per90, shots, shots_on_target, shots_on_target_pct, shots_per90, sot_per90, goals_per_shot, goals_per_sot, avg_shot_distance, npxg_per_shot, xg_net, npxg_net, passes_completed, passes_attempted, pass_completion_pct, passes_total_dist, passes_prog_dist, passes_short_pct, passes_medium_pct, passes_long_completed, passes_long_attempted, passes_long_pct, key_passes, passes_final_third, passes_penalty_area, crosses_penalty_area, progressive_passes, xa_pass, sca, sca_per90, sca_pass_live, sca_pass_dead, sca_take_on, sca_shot, gca, gca_per90, gca_pass_live, gca_take_on, tackles, tackles_won, tackles_def_3rd, tackles_mid_3rd, tackles_att_3rd, challenge_tackles, challenges, challenge_tackles_pct, blocks, blocked_shots, blocked_passes, interceptions, tkl_int, clearances, errors, touches, touches_def_pen, touches_def_3rd, touches_mid_3rd, touches_att_3rd, touches_att_pen, take_ons_att, take_ons_succ, take_ons_succ_pct, take_ons_tackled, carries, carries_prog_dist, progressive_carries, carries_final_third, carries_penalty_area, miscontrols, dispossessed, progressive_passes_received, fouls_committed, fouls_drawn, offsides, crosses, pens_won, pens_conceded, own_goals, ball_recoveries, aerials_won, aerials_lost, aerials_won_pct, fbref_player_id, fetched_at, updated_at) FROM stdin;
\.


--
-- Data for Name: player_heatmap; Type: TABLE DATA; Schema: public; Owner: football
--

COPY public.player_heatmap (id, player_id, season, league, points, point_count, position_played, source, fetched_at) FROM stdin;
\.


--
-- Data for Name: player_matches; Type: TABLE DATA; Schema: public; Owner: football
--

COPY public.player_matches (id, player_id, event_id, date, season, tournament, home_team, away_team, home_score, away_score, rating, minutes_played, goals, assists, yellow_card, red_card, source, fetched_at) FROM stdin;
\.


--
-- Data for Name: player_national_stats; Type: TABLE DATA; Schema: public; Owner: football
--

COPY public.player_national_stats (id, player_id, national_team, season, appearances, minutes, goals, assists, rating, yellow_cards, red_cards, raw_data, source, fetched_at, updated_at) FROM stdin;
\.


--
-- Data for Name: player_scouting_index; Type: TABLE DATA; Schema: public; Owner: football
--

COPY public.player_scouting_index (id, player_id, season, position_group, finishing_index, creativity_index, pressing_index, carrying_index, defending_index, buildup_index, overall_index, finishing_pct, creativity_pct, pressing_pct, carrying_pct, defending_pct, buildup_pct, heading_score, xg_per90, xa_per90, npxg_per90, sca_per90, gca_per90, progressive_carries_per90, progressive_passes_per90, tackles_won_per90, interceptions_per90, aerials_won_pct, take_ons_succ_pct, pass_completion_pct, goals_per_shot, ball_recoveries_per90, crosses_per90, sources_used, data_confidence, minutes_sample, computed_at, updated_at) FROM stdin;
\.


--
-- Data for Name: player_season_stats; Type: TABLE DATA; Schema: public; Owner: football
--

COPY public.player_season_stats (id, player_id, season, league, source, sofascore_rating, appearances, matches_started, minutes_played, goals, assists, goals_assists_sum, shots_total, shots_on_target, shots_off_target, shots_inside_box, shots_outside_box, big_chances_created, big_chances_missed, goal_conversion_pct, headed_goals, left_foot_goals, right_foot_goals, goals_inside_box, goals_outside_box, free_kick_goals, penalty_goals, penalty_taken, penalty_won, own_goals, xg, xa, xg_per90, xa_per90, npxg_per90, xgchain_per90, xgbuildup_per90, accurate_passes, inaccurate_passes, total_passes, pass_accuracy_pct, accurate_own_half_passes, accurate_opp_half_passes, accurate_final_third_passes, accurate_long_balls, long_ball_accuracy_pct, total_long_balls, accurate_crosses, cross_accuracy_pct, total_crosses, key_passes, pass_to_assist, chipped_passes, progressive_passes, progressive_carries, progressive_passes_received, touches_att_pen, successful_dribbles, dribble_success_pct, dribbled_past, dispossessed, ground_duels_won, ground_duels_won_pct, aerial_duels_won, aerial_duels_lost, aerial_duels_won_pct, total_duels_won, total_duels_won_pct, total_contest, tackles, tackles_won, tackles_won_pct, interceptions, clearances, blocked_shots, errors_led_to_goal, errors_led_to_shot, ball_recovery, possession_won_att_third, pressures, pressure_regains, touches, possession_lost, shot_from_set_piece, yellow_cards, yellow_red_cards, red_cards, fouls_committed, fouls_won, offsides, hit_woodwork, saves, goals_conceded, goals_conceded_inside_box, goals_conceded_outside_box, clean_sheets, penalty_saved, penalty_faced, high_claims, punches, runs_out, successful_runs_out, saved_shots_inside_box, saved_shots_outside_box, fanta_media, fanta_media_mv, fanta_gol, fanta_assist, fanta_ammonizioni, fanta_espulsioni, fanta_rigori_segnati, fanta_rigori_sbagliati, fanta_autogol, fanta_presenze, tournament_id, season_id, fetched_at, updated_at) FROM stdin;
\.


--
-- Data for Name: player_sofascore_stats; Type: TABLE DATA; Schema: public; Owner: football
--

COPY public.player_sofascore_stats (id, player_id, season, league, sofascore_rating, appearances, matches_started, minutes_played, goals, assists, goals_assists_sum, shots_total, shots_on_target, shots_off_target, big_chances_created, big_chances_missed, goal_conversion_pct, headed_goals, penalty_goals, penalty_won, xg, xa, xg_per90, xa_per90, accurate_passes, inaccurate_passes, total_passes, pass_accuracy_pct, accurate_long_balls, long_ball_accuracy_pct, total_long_balls, accurate_crosses, cross_accuracy_pct, total_crosses, key_passes, accurate_own_half_passes, accurate_opp_half_passes, accurate_final_third_passes, successful_dribbles, dribble_attempts, dribble_success_pct, dribbled_past, dispossessed, ground_duels_won, ground_duels_won_pct, aerial_duels_won, aerial_duels_lost, aerial_duels_won_pct, total_duels_won, total_duels_won_pct, total_contest, tackles, tackles_won, tackles_won_pct, interceptions, clearances, blocked_shots, errors_led_to_goal, errors_led_to_shot, ball_recovery, possession_won_att_third, touches, possession_lost, yellow_cards, yellow_red_cards, red_cards, fouls_committed, fouls_won, offsides, hit_woodwork, saves, goals_conceded, clean_sheets, penalty_saved, penalty_faced, high_claims, punches, tournament_id, season_id, season_club, attributes_raw, attributes_avg_raw, fetched_at, updated_at) FROM stdin;
\.


--
-- Data for Name: scouting_players; Type: TABLE DATA; Schema: public; Owner: football
--

COPY public.scouting_players (id, api_football_id, transfermarkt_id, fbref_id, understat_id, sofascore_id, name, birth_date, "position", position_detail, club, club_id, nationality, age, preferred_foot, height, weight, jersey_number, gender, market_value, contract_until, sofascore_rating, last_updated_understat, last_updated_fbref, last_updated_api_football, last_updated_statsbomb, last_updated_sofascore, updated_at) FROM stdin;
\.


--
-- Data for Name: team_traits; Type: TABLE DATA; Schema: public; Owner: football
--

COPY public.team_traits (id, team_id, trait_type, description, priority) FROM stdin;
\.


--
-- Name: clubs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: football
--

SELECT pg_catalog.setval('public.clubs_id_seq', 1, false);


--
-- Name: my_players_id_seq; Type: SEQUENCE SET; Schema: public; Owner: football
--

SELECT pg_catalog.setval('public.my_players_id_seq', 1, false);


--
-- Name: my_team_id_seq; Type: SEQUENCE SET; Schema: public; Owner: football
--

SELECT pg_catalog.setval('public.my_team_id_seq', 1, false);


--
-- Name: player_career_id_seq; Type: SEQUENCE SET; Schema: public; Owner: football
--

SELECT pg_catalog.setval('public.player_career_id_seq', 1, false);


--
-- Name: player_fbref_match_logs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: football
--

SELECT pg_catalog.setval('public.player_fbref_match_logs_id_seq', 1, false);


--
-- Name: player_fbref_stats_id_seq; Type: SEQUENCE SET; Schema: public; Owner: football
--

SELECT pg_catalog.setval('public.player_fbref_stats_id_seq', 1, false);


--
-- Name: player_heatmap_id_seq; Type: SEQUENCE SET; Schema: public; Owner: football
--

SELECT pg_catalog.setval('public.player_heatmap_id_seq', 1, false);


--
-- Name: player_matches_id_seq; Type: SEQUENCE SET; Schema: public; Owner: football
--

SELECT pg_catalog.setval('public.player_matches_id_seq', 1, false);


--
-- Name: player_national_stats_id_seq; Type: SEQUENCE SET; Schema: public; Owner: football
--

SELECT pg_catalog.setval('public.player_national_stats_id_seq', 1, false);


--
-- Name: player_scouting_index_id_seq; Type: SEQUENCE SET; Schema: public; Owner: football
--

SELECT pg_catalog.setval('public.player_scouting_index_id_seq', 1, false);


--
-- Name: player_season_stats_id_seq; Type: SEQUENCE SET; Schema: public; Owner: football
--

SELECT pg_catalog.setval('public.player_season_stats_id_seq', 1, false);


--
-- Name: player_sofascore_stats_id_seq; Type: SEQUENCE SET; Schema: public; Owner: football
--

SELECT pg_catalog.setval('public.player_sofascore_stats_id_seq', 1, false);


--
-- Name: scouting_players_id_seq; Type: SEQUENCE SET; Schema: public; Owner: football
--

SELECT pg_catalog.setval('public.scouting_players_id_seq', 1, false);


--
-- Name: team_traits_id_seq; Type: SEQUENCE SET; Schema: public; Owner: football
--

SELECT pg_catalog.setval('public.team_traits_id_seq', 1, false);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: clubs clubs_pkey; Type: CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.clubs
    ADD CONSTRAINT clubs_pkey PRIMARY KEY (id);


--
-- Name: my_players my_players_pkey; Type: CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.my_players
    ADD CONSTRAINT my_players_pkey PRIMARY KEY (id);


--
-- Name: my_team my_team_pkey; Type: CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.my_team
    ADD CONSTRAINT my_team_pkey PRIMARY KEY (id);


--
-- Name: player_career player_career_pkey; Type: CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_career
    ADD CONSTRAINT player_career_pkey PRIMARY KEY (id);


--
-- Name: player_fbref_match_logs player_fbref_match_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_fbref_match_logs
    ADD CONSTRAINT player_fbref_match_logs_pkey PRIMARY KEY (id);


--
-- Name: player_fbref_stats player_fbref_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_fbref_stats
    ADD CONSTRAINT player_fbref_stats_pkey PRIMARY KEY (id);


--
-- Name: player_heatmap player_heatmap_pkey; Type: CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_heatmap
    ADD CONSTRAINT player_heatmap_pkey PRIMARY KEY (id);


--
-- Name: player_matches player_matches_pkey; Type: CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_matches
    ADD CONSTRAINT player_matches_pkey PRIMARY KEY (id);


--
-- Name: player_national_stats player_national_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_national_stats
    ADD CONSTRAINT player_national_stats_pkey PRIMARY KEY (id);


--
-- Name: player_scouting_index player_scouting_index_pkey; Type: CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_scouting_index
    ADD CONSTRAINT player_scouting_index_pkey PRIMARY KEY (id);


--
-- Name: player_season_stats player_season_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_season_stats
    ADD CONSTRAINT player_season_stats_pkey PRIMARY KEY (id);


--
-- Name: player_sofascore_stats player_sofascore_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_sofascore_stats
    ADD CONSTRAINT player_sofascore_stats_pkey PRIMARY KEY (id);


--
-- Name: scouting_players scouting_players_pkey; Type: CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.scouting_players
    ADD CONSTRAINT scouting_players_pkey PRIMARY KEY (id);


--
-- Name: team_traits team_traits_pkey; Type: CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.team_traits
    ADD CONSTRAINT team_traits_pkey PRIMARY KEY (id);


--
-- Name: player_fbref_match_logs uq_fbref_matchlog_player_date_comp; Type: CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_fbref_match_logs
    ADD CONSTRAINT uq_fbref_matchlog_player_date_comp UNIQUE (player_id, date, comp);


--
-- Name: player_fbref_stats uq_fbref_player_season_league; Type: CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_fbref_stats
    ADD CONSTRAINT uq_fbref_player_season_league UNIQUE (player_id, season, league);


--
-- Name: player_heatmap uq_heatmap_player_season_league; Type: CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_heatmap
    ADD CONSTRAINT uq_heatmap_player_season_league UNIQUE (player_id, season, league, source);


--
-- Name: player_national_stats uq_national_player_team_season; Type: CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_national_stats
    ADD CONSTRAINT uq_national_player_team_season UNIQUE (player_id, national_team, season, source);


--
-- Name: player_matches uq_player_event; Type: CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_matches
    ADD CONSTRAINT uq_player_event UNIQUE (player_id, event_id);


--
-- Name: player_season_stats uq_player_season_league_source; Type: CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_season_stats
    ADD CONSTRAINT uq_player_season_league_source UNIQUE (player_id, season, league, source);


--
-- Name: player_scouting_index uq_scouting_index_player_season; Type: CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_scouting_index
    ADD CONSTRAINT uq_scouting_index_player_season UNIQUE (player_id, season);


--
-- Name: player_sofascore_stats uq_sofascore_player_season_league; Type: CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_sofascore_stats
    ADD CONSTRAINT uq_sofascore_player_season_league UNIQUE (player_id, season, league);


--
-- Name: ix_clubs_id; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_clubs_id ON public.clubs USING btree (id);


--
-- Name: ix_clubs_league_key; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_clubs_league_key ON public.clubs USING btree (league_key);


--
-- Name: ix_clubs_name; Type: INDEX; Schema: public; Owner: football
--

CREATE UNIQUE INDEX ix_clubs_name ON public.clubs USING btree (name);


--
-- Name: ix_fbref_matchlog_player_date; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_fbref_matchlog_player_date ON public.player_fbref_match_logs USING btree (player_id, date);


--
-- Name: ix_fbref_stats_player_season; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_fbref_stats_player_season ON public.player_fbref_stats USING btree (player_id, season);


--
-- Name: ix_my_players_id; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_my_players_id ON public.my_players USING btree (id);


--
-- Name: ix_my_team_id; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_my_team_id ON public.my_team USING btree (id);


--
-- Name: ix_player_career_id; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_player_career_id ON public.player_career USING btree (id);


--
-- Name: ix_player_career_player_id; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_player_career_player_id ON public.player_career USING btree (player_id);


--
-- Name: ix_player_fbref_match_logs_date; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_player_fbref_match_logs_date ON public.player_fbref_match_logs USING btree (date);


--
-- Name: ix_player_fbref_match_logs_id; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_player_fbref_match_logs_id ON public.player_fbref_match_logs USING btree (id);


--
-- Name: ix_player_fbref_match_logs_player_id; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_player_fbref_match_logs_player_id ON public.player_fbref_match_logs USING btree (player_id);


--
-- Name: ix_player_fbref_stats_id; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_player_fbref_stats_id ON public.player_fbref_stats USING btree (id);


--
-- Name: ix_player_fbref_stats_player_id; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_player_fbref_stats_player_id ON public.player_fbref_stats USING btree (player_id);


--
-- Name: ix_player_heatmap_id; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_player_heatmap_id ON public.player_heatmap USING btree (id);


--
-- Name: ix_player_heatmap_player_id; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_player_heatmap_player_id ON public.player_heatmap USING btree (player_id);


--
-- Name: ix_player_match_player_date; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_player_match_player_date ON public.player_matches USING btree (player_id, date);


--
-- Name: ix_player_matches_date; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_player_matches_date ON public.player_matches USING btree (date);


--
-- Name: ix_player_matches_event_id; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_player_matches_event_id ON public.player_matches USING btree (event_id);


--
-- Name: ix_player_matches_id; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_player_matches_id ON public.player_matches USING btree (id);


--
-- Name: ix_player_matches_player_id; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_player_matches_player_id ON public.player_matches USING btree (player_id);


--
-- Name: ix_player_national_stats_id; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_player_national_stats_id ON public.player_national_stats USING btree (id);


--
-- Name: ix_player_national_stats_player_id; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_player_national_stats_player_id ON public.player_national_stats USING btree (player_id);


--
-- Name: ix_player_scouting_index_id; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_player_scouting_index_id ON public.player_scouting_index USING btree (id);


--
-- Name: ix_player_scouting_index_player_id; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_player_scouting_index_player_id ON public.player_scouting_index USING btree (player_id);


--
-- Name: ix_player_season_stats_id; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_player_season_stats_id ON public.player_season_stats USING btree (id);


--
-- Name: ix_player_season_stats_player_id; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_player_season_stats_player_id ON public.player_season_stats USING btree (player_id);


--
-- Name: ix_player_sofascore_stats_id; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_player_sofascore_stats_id ON public.player_sofascore_stats USING btree (id);


--
-- Name: ix_player_sofascore_stats_player_id; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_player_sofascore_stats_player_id ON public.player_sofascore_stats USING btree (player_id);


--
-- Name: ix_scouting_players_api_football_id; Type: INDEX; Schema: public; Owner: football
--

CREATE UNIQUE INDEX ix_scouting_players_api_football_id ON public.scouting_players USING btree (api_football_id);


--
-- Name: ix_scouting_players_birth_date; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_scouting_players_birth_date ON public.scouting_players USING btree (birth_date);


--
-- Name: ix_scouting_players_fbref_id; Type: INDEX; Schema: public; Owner: football
--

CREATE UNIQUE INDEX ix_scouting_players_fbref_id ON public.scouting_players USING btree (fbref_id);


--
-- Name: ix_scouting_players_id; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_scouting_players_id ON public.scouting_players USING btree (id);


--
-- Name: ix_scouting_players_name; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_scouting_players_name ON public.scouting_players USING btree (name);


--
-- Name: ix_scouting_players_sofascore_id; Type: INDEX; Schema: public; Owner: football
--

CREATE UNIQUE INDEX ix_scouting_players_sofascore_id ON public.scouting_players USING btree (sofascore_id);


--
-- Name: ix_scouting_players_transfermarkt_id; Type: INDEX; Schema: public; Owner: football
--

CREATE UNIQUE INDEX ix_scouting_players_transfermarkt_id ON public.scouting_players USING btree (transfermarkt_id);


--
-- Name: ix_scouting_players_understat_id; Type: INDEX; Schema: public; Owner: football
--

CREATE UNIQUE INDEX ix_scouting_players_understat_id ON public.scouting_players USING btree (understat_id);


--
-- Name: ix_season_stats_player_season; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_season_stats_player_season ON public.player_season_stats USING btree (player_id, season);


--
-- Name: ix_sofascore_stats_player_season; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_sofascore_stats_player_season ON public.player_sofascore_stats USING btree (player_id, season);


--
-- Name: ix_team_traits_id; Type: INDEX; Schema: public; Owner: football
--

CREATE INDEX ix_team_traits_id ON public.team_traits USING btree (id);


--
-- Name: my_players my_players_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.my_players
    ADD CONSTRAINT my_players_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.my_team(id) ON DELETE CASCADE;


--
-- Name: player_career player_career_player_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_career
    ADD CONSTRAINT player_career_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.scouting_players(id) ON DELETE CASCADE;


--
-- Name: player_fbref_match_logs player_fbref_match_logs_player_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_fbref_match_logs
    ADD CONSTRAINT player_fbref_match_logs_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.scouting_players(id) ON DELETE CASCADE;


--
-- Name: player_fbref_stats player_fbref_stats_player_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_fbref_stats
    ADD CONSTRAINT player_fbref_stats_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.scouting_players(id) ON DELETE CASCADE;


--
-- Name: player_heatmap player_heatmap_player_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_heatmap
    ADD CONSTRAINT player_heatmap_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.scouting_players(id) ON DELETE CASCADE;


--
-- Name: player_matches player_matches_player_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_matches
    ADD CONSTRAINT player_matches_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.scouting_players(id) ON DELETE CASCADE;


--
-- Name: player_national_stats player_national_stats_player_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_national_stats
    ADD CONSTRAINT player_national_stats_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.scouting_players(id) ON DELETE CASCADE;


--
-- Name: player_scouting_index player_scouting_index_player_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_scouting_index
    ADD CONSTRAINT player_scouting_index_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.scouting_players(id) ON DELETE CASCADE;


--
-- Name: player_season_stats player_season_stats_player_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_season_stats
    ADD CONSTRAINT player_season_stats_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.scouting_players(id) ON DELETE CASCADE;


--
-- Name: player_sofascore_stats player_sofascore_stats_player_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.player_sofascore_stats
    ADD CONSTRAINT player_sofascore_stats_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.scouting_players(id) ON DELETE CASCADE;


--
-- Name: scouting_players scouting_players_club_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.scouting_players
    ADD CONSTRAINT scouting_players_club_id_fkey FOREIGN KEY (club_id) REFERENCES public.clubs(id);


--
-- Name: team_traits team_traits_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: football
--

ALTER TABLE ONLY public.team_traits
    ADD CONSTRAINT team_traits_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.my_team(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict Dijy8hNaQiBtDfkELbqkhac8vXBqjHeE3K4rBwogNW00sQpmERS5PnTxWnMXTDN

