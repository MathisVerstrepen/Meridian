import { FileType } from '@/types/enums';

export interface File {
    id: string; // UUID
    name: string;
    size: number;
    type: FileType;
}
