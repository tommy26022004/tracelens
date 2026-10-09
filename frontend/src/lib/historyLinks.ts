type HistoryLink = { id: string; related_id?: string; application_id?: string };

export function linkedFollowUps<T extends HistoryLink>(records: T[], entry: HistoryLink): T[] {
    return records.filter((linked) => linked.id !== entry.id && Boolean(linked.related_id) &&
        (linked.related_id === entry.id || Boolean(entry.application_id) && linked.related_id === entry.application_id));
}
